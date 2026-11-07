# -*- coding: utf-8 -*-
"""
dump-edit.py —— 直接修改 1024 字节 M1 dump 中的字段，自动重算所有校验。

用法示例：
  # 查看
  python dump-edit.py dumps/演示数据-张三.dump --show

  # 改金额（水控1/水控2/消费钱包）
  python dump-edit.py dumps/演示数据-张三.dump -o out.dump \
      --water1 20.00 --water2 5.00 --balance 300.0 --cash 0.5 \
      --day 12.5 --time "2026-11-07 12:00:00"

  # 模拟一次消费 3 元（写进另一条记录，序号+1，当日累计+3）
  python dump-edit.py dumps/演示数据-张三.dump -o out.dump --spend 3.0

  # 模拟充值 100 元
  python dump-edit.py dumps/演示数据-张三.dump -o out.dump --topup 100

  # 改卡面信息
  python dump-edit.py in.dump -o out.dump --name 张三 --cardno 123456 --role 0x09 --date 2026-08-21

所有金额单位：元（脚本内部换算成分/角）。
"""
import argparse
import datetime
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

EXAMPLES = """常用示例：
  python scripts/dump-edit.py dumps/演示数据-张三.dump --show
  python scripts/dump-edit.py in.dump -o out.dump --water1 20 --water2 5
  python scripts/dump-edit.py in.dump -o out.dump --spend 3.0
  python scripts/dump-edit.py in.dump -o out.dump --topup 100
  python scripts/dump-edit.py in.dump -o out.dump --name 李四 --cardno 654321
  python scripts/dump-edit.py in.dump -o out.dump --clear-sectors 2,3 --water2 655.35
所有金额单位：元（脚本内部换算成分/角）。"""

T1 = bytes([0x00, 0x01, 0x20, 0x00, 0x00, 0x04])   # S9 KeyA = S8 KeyA ^ T1
T2 = bytes([0x60, 0x84, 0x2D, 0x00, 0x00, 0x0C])   # KeyB = KeyA ^ T2


# ---------------- 基础工具 ----------------

def blk(d, s, b):
    return d[s * 64 + b * 16: s * 64 + b * 16 + 16]


def put_blk(d, s, b, data):
    if len(data) != 16:
        raise ValueError("块长度必须是 16 字节")
    d[s * 64 + b * 16: s * 64 + b * 16 + 16] = data


def crc16_water1(balance_bytes):
    crc, poly = 0x0000, 0x1021
    for b in balance_bytes:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc ^ 0x20F5


def yuan_to_fen(s):
    return int(round(float(s) * 100))


def yuan_to_jiao(s):
    return int(round(float(s) * 10))


def parse_role(s):
    s = str(s)
    return int(s, 16) if s.lower().startswith("0x") else int(s)


def parse_time(s):
    """'YYYY-MM-DD HH:MM:SS' -> 6 字节 (年-2000,月,日,时,分,秒)"""
    dt = datetime.datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S")
    if not (2000 <= dt.year <= 2255):
        raise ValueError("年份需在 2000~2255 之间")
    return bytes([dt.year - 2000, dt.month, dt.day, dt.hour, dt.minute, dt.second])


def parse_date(s):
    dt = datetime.datetime.strptime(s.strip(), "%Y-%m-%d")
    return bytes([dt.year - 2000, dt.month, dt.day])


def name_to_bytes(name):
    """姓名：GBK 编码，最多 8 字节，不足补 0x20"""
    b = name.encode("gbk")
    if len(b) > 8:
        raise ValueError("姓名 GBK 编码后超过 8 字节（约 4 个汉字）")
    return b + b"\x20" * (8 - len(b))


# ---------------- 各区块写入 ----------------

def set_water1(d, yuan):
    """Sector 9：Block37、Block38 镜像写入 10 AC 0C AF + 余额(fen,BE) + CRC + 0"""
    fen = yuan_to_fen(yuan)
    if not 0 <= fen <= 65535:
        raise ValueError("水控1 金额范围 0 ~ 655.35 元")
    bal = fen.to_bytes(2, "big")
    block = bytes.fromhex("10AC0CAF") + bal + crc16_water1(bal).to_bytes(2, "big") + bytes(8)
    put_blk(d, 9, 1, block)
    put_blk(d, 9, 2, block)
    return fen


def set_water2(d, yuan, count=None, counter=None):
    """Sector 4：Block16 余额(fen,LE)，并重算 b0/b1/b5/b13/b15"""
    fen = yuan_to_fen(yuan)
    if not 0 <= fen <= 65535:
        raise ValueError("水控2 金额范围 0 ~ 655.35 元")
    b = bytearray(blk(d, 4, 0))
    b[2:4] = fen.to_bytes(2, "little")
    if count is not None:
        if not 0 <= count <= 255:
            raise ValueError("--water2-count 范围 0~255")
        b[4] = count
    if counter is not None:
        if not 0 <= counter <= 255:
            raise ValueError("--water2-counter 范围 0~255")
        b[10] = counter
    # 余额 > 0 视为已使用卡（必须在算 b0 之前设置 b11）
    if fen > 0 and b[11] == 0:
        b[11] = 1
    # b13 = b10+1（已用卡）；初始未用卡时 b11=0 则 b13 = b10（必须在算 b0 之前）
    b[13] = (b[10] + 1) & 0xFF if b[11] == 1 else b[10]
    # b1 = (b2 + b3 + b4) & 0xFF
    b[1] = (b[2] + b[3] + b[4]) & 0xFF
    # b5 = ~b1（必须在算 b0 之前，因为 b0 要异或 b1..b14）
    b[5] = (~b[1]) & 0xFF
    # b0 = XOR(b1..b14)
    x = 0
    for i in range(1, 15):
        x ^= b[i]
    b[0] = x
    # b15 = ~sum(b1..b14)
    b[15] = (~sum(b[1:15])) & 0xFF
    put_blk(d, 4, 0, b)
    put_blk(d, 4, 2, b)   # B18 是 B16 的镜像块，必须同步
    return fen


def wallet_records(d):
    recs = {}
    for s in (2, 3):
        b0, b1 = blk(d, s, 0), blk(d, s, 1)
        recs[s] = {
            "cash": int.from_bytes(b0[0:4], "big"),
            "balance": int.from_bytes(b0[4:8], "big"),
            "seq": int.from_bytes(b0[8:12], "big"),
            "time": bytes(b1[0:6]),
            "day": int.from_bytes(b1[9:11], "big"),
        }
    return recs


def write_wallet_record(d, sector, rec):
    b0 = bytearray(blk(d, sector, 0))
    b1 = bytearray(blk(d, sector, 1))
    b0[0:4] = (rec["cash"] & 0xFFFFFFFF).to_bytes(4, "big")
    b0[4:8] = (rec["balance"] & 0xFFFFFFFF).to_bytes(4, "big")
    b0[8:12] = (rec["seq"] & 0xFFFFFFFF).to_bytes(4, "big")
    b1[0:6] = rec["time"]
    b1[9:11] = (rec["day"] & 0xFFFF).to_bytes(2, "big")
    put_blk(d, sector, 0, b0)
    put_blk(d, sector, 1, b1)


def set_wallet(d, balance_yuan=None, cash_yuan=None, day_yuan=None,
               time_str=None, seq=None, sector="older"):
    recs = wallet_records(d)
    newest = 2 if recs[2]["seq"] > recs[3]["seq"] else 3
    target = {"newest": newest, "older": 5 - newest}.get(sector, sector)
    target = int(target)
    if target not in (2, 3):
        raise ValueError("--wallet-sector 只能是 2 / 3 / newest / older")

    rec = dict(recs[target])
    if balance_yuan is not None:
        rec["balance"] = yuan_to_jiao(balance_yuan)
    if cash_yuan is not None:
        cash = yuan_to_jiao(cash_yuan)
        if not 0 <= cash <= 0xFFFFFFFF:
            raise ValueError("现金不能为负")
        rec["cash"] = cash
    if day_yuan is not None:
        day = yuan_to_jiao(day_yuan)
        if not 0 <= day <= 65535:
            raise ValueError("当日累计范围 0 ~ 6553.5 元")
        rec["day"] = day
    if time_str:
        rec["time"] = parse_time(time_str)
    if seq is not None:
        rec["seq"] = seq
    write_wallet_record(d, target, rec)
    return rec, target


def apply_transaction(d, amount_yuan, topup=False, time_str=None):
    """消费/充值：写到较旧的那个扇区，序号 = max+1"""
    recs = wallet_records(d)
    newest = 2 if recs[2]["seq"] > recs[3]["seq"] else 3
    target = 5 - newest
    base = dict(recs[newest])

    delta = yuan_to_jiao(amount_yuan)
    if topup:
        base["balance"] += delta
    else:
        base["balance"] -= delta
    if base["balance"] < 0:
        raise ValueError("余额不足，扣款后为负")
    if not topup:
        base["day"] += delta
    base["seq"] = max(recs[2]["seq"], recs[3]["seq"]) + 1
    base["time"] = parse_time(time_str) if time_str else datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base["time"] = base["time"] if isinstance(base["time"], (bytes, bytearray)) else parse_time(base["time"])
    write_wallet_record(d, target, base)
    return base, target


def clear_sectors(d, sectors):
    """清空指定扇区的数据块（0~2），保留第 3 块的密钥/访问位。"""
    for sec in sectors:
        if not 0 <= sec <= 15:
            raise ValueError(f"扇区号 {sec} 超出 0~15")
        for b in range(3):
            put_blk(d, sec, b, bytes(16))
    return sectors


def set_info(d, name=None, cardno=None, role=None, date=None):
    b0 = bytearray(blk(d, 1, 0))
    b1 = bytearray(blk(d, 1, 1))
    if name is not None:
        try:
            b0[5:13] = name_to_bytes(name)
        except UnicodeEncodeError:
            raise ValueError("姓名无法用 GBK 编码")
    if cardno is not None:
        if not 0 <= cardno <= 0xFFFFFF:
            raise ValueError("卡号范围 0 ~ 16777215")
        b0[1:4] = cardno.to_bytes(3, "big")
    if role is not None:
        if not 0 <= role <= 255:
            raise ValueError("级别范围 0~255")
        b0[4] = role
    if date is not None:
        b1[0:3] = parse_date(date)
    put_blk(d, 1, 0, b0)
    put_blk(d, 1, 1, b1)


# ---------------- 展示 ----------------

def show(d):
    b0, b1, b2 = blk(d, 1, 0), blk(d, 1, 1), blk(d, 1, 2)
    cardno = (b0[1] << 16) | (b0[2] << 8) | b0[3]
    name = ""
    try:
        name = b0[5:13].decode("gbk", "replace").strip()
    except Exception:
        pass
    print(f"UID          : {d[0:4].hex(' ').upper()}")
    print(f"卡号/级别     : {cardno} / 0x{b0[4]:02X}")
    print(f"姓名          : {name}")
    print(f"开卡日期      : 20{b1[0]:02d}-{b1[1]:02d}-{b1[2]:02d}")
    print(f"状态字节 S1B2[0]: 0x{b2[0]:02X}")

    recs = wallet_records(d)
    for s in (2, 3):
        r = recs[s]
        t = r["time"]
        print(f"S{s} 记录       : 20{t[0]:02d}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
              f"  余额 {r['balance']/10:.1f} 元  现金 {r['cash']/10:.1f} 元"
              f"  当日 {r['day']/10:.1f} 元  序号 {r['seq']}")
    newest = 2 if recs[2]["seq"] > recs[3]["seq"] else 3
    print(f"最新记录      : S{newest}")

    w2 = blk(d, 4, 0)
    fen = int.from_bytes(w2[2:4], "little")
    ok1 = w2[1] == ((w2[2] + w2[3] + w2[4]) & 0xFF)
    ok2 = w2[5] == ((~w2[1]) & 0xFF)
    ok3 = w2[0] == _xor(w2[1:15])
    ok4 = w2[15] == ((~sum(w2[1:15])) & 0xFF)
    print(f"水控2 (S4B0)  : {fen/100:.2f} 元  校验 {'通过' if all([ok1,ok2,ok3,ok4]) else '失败'}"
          f"  b10=0x{w2[10]:02X} b11=0x{w2[11]:02X} b13=0x{w2[13]:02X}")

    w1 = blk(d, 9, 1)
    if w1[0:4] == bytes.fromhex("10AC0CAF"):
        bal = int.from_bytes(w1[4:6], "big")
        crc = int.from_bytes(w1[6:8], "big")
        ok = crc == crc16_water1(w1[4:6])
        mirror = bytes(blk(d, 9, 1)) == bytes(blk(d, 9, 2))
        print(f"水控1 (S9B1)  : {bal/100:.2f} 元  CRC {'通过' if ok else '失败'}"
              f"  B37=B38 {'是' if mirror else '否'}")
    else:
        print("水控1 (S9B1)  : 未初始化")


def _xor(data):
    x = 0
    for b in data:
        x ^= b
    return x


# ---------------- 主流程 ----------------

def main():
    ap = argparse.ArgumentParser(
        description="修改 1024 字节 M1 dump 的字段并自动重算校验",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXAMPLES,
    )
    ap.add_argument("input", help="输入 dump 文件（1024 字节）")
    ap.add_argument("-o", "--out", help="输出文件（默认 输入名_edited.dump）")
    ap.add_argument("--inplace", action="store_true", help="直接覆盖输入文件")
    ap.add_argument("--show", action="store_true", help="打印当前内容（可单独使用）")

    g1 = ap.add_argument_group("水控")
    g1.add_argument("--water1", type=float, help="水控1 余额（元，0~655.35）")
    g1.add_argument("--water2", type=float, help="水控2 余额（元，0~655.35）")
    g1.add_argument("--water2-count", type=int, help="水控2 交易次数 b4（0~255）")
    g1.add_argument("--water2-counter", type=int, help="水控2 写计数 b10（0~255）")
    g1.add_argument("--clear-sectors", help="清空指定扇区数据块（保留密钥区），如 2,3")

    g2 = ap.add_argument_group("消费钱包")
    g2.add_argument("--balance", type=float, help="余额（元）")
    g2.add_argument("--cash", type=float, help="现金/补贴（元，4 字节大端，可超过 25.5）")
    g2.add_argument("--day", type=float, help="当日累计（元）")
    g2.add_argument("--time", help='时间 "YYYY-MM-DD HH:MM:SS"')
    g2.add_argument("--seq", type=int, help="记录序号 B")
    g2.add_argument("--wallet-sector", default="older",
                    help="写到哪个扇区：2 / 3 / newest / older（默认 older）")
    g2.add_argument("--spend", type=float, help="模拟消费金额（元）")
    g2.add_argument("--topup", type=float, help="模拟充值金额（元）")

    g3 = ap.add_argument_group("卡面信息")
    g3.add_argument("--name", help="姓名（GBK，最多 8 字节）")
    g3.add_argument("--cardno", type=int, help="卡号（十进制）")
    g3.add_argument("--role", help="级别，如 9 或 0x09")
    g3.add_argument("--date", help='开卡日期 "YYYY-MM-DD"')

    # 不带任何参数运行时，直接显示用法
    if len(sys.argv) == 1:
        ap.print_help()
        sys.exit(0)

    args = ap.parse_args()

    with open(args.input, "rb") as f:
        data = bytearray(f.read())
    if len(data) != 1024:
        print(f"错误：{args.input} 不是 1024 字节（实际 {len(data)}）", file=sys.stderr)
        sys.exit(1)

    changed = []
    try:
        if args.clear_sectors:
            secs = [int(x) for x in str(args.clear_sectors).replace("，", ",").split(",") if x.strip() != ""]
            clear_sectors(data, secs)
            changed.append("清空扇区 " + ",".join(str(x) for x in secs))
        if args.water1 is not None:
            set_water1(data, args.water1)
            changed.append("水控1")
        if args.water2 is not None or args.water2_count is not None or args.water2_counter is not None:
            fen = set_water2(
                data,
                args.water2 if args.water2 is not None else int.from_bytes(blk(data, 4, 0)[2:4], "little") / 100,
                args.water2_count, args.water2_counter,
            )
            changed.append("水控2")
        if args.spend is not None and args.topup is not None:
            raise ValueError("--spend 与 --topup 不能同时使用")
        if args.spend is not None:
            apply_transaction(data, args.spend, topup=False, time_str=args.time)
            changed.append(f"消费 {args.spend} 元")
        if args.topup is not None:
            apply_transaction(data, args.topup, topup=True, time_str=args.time)
            changed.append(f"充值 {args.topup} 元")
        if any(v is not None for v in (args.balance, args.cash, args.day, args.time, args.seq)) \
                and args.spend is None and args.topup is None:
            set_wallet(data,
                       balance_yuan=args.balance, cash_yuan=args.cash, day_yuan=args.day,
                       time_str=args.time, seq=args.seq, sector=args.wallet_sector)
            changed.append("消费钱包")
        if any(v is not None for v in (args.name, args.cardno, args.role, args.date)):
            set_info(data, name=args.name, cardno=args.cardno,
                     role=parse_role(args.role) if args.role is not None else None,
                     date=args.date)
            changed.append("卡面信息")
    except ValueError as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)

    if changed:
        out = args.input if args.inplace else (args.out or args.input.rsplit(".", 1)[0] + "_edited.dump")
        with open(out, "wb") as f:
            f.write(data)
        print("已修改：" + "、".join(changed))
        print("输出：" + out)
        print()
    show(data)


if __name__ == "__main__":
    main()
