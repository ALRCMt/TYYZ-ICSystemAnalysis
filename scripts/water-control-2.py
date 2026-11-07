def water2_block(yuan: float, b4: int = 0x00, counter: int = 0xFA,
                 used: bool = True) -> bytes:
    """余额(元) + b4(交易次数) + 计数器 → 完整 16 字节块

    used=True  机器写过的块：b11=01, b13=(b10+1)&0xFF
    used=False 未使用初始态：b11=00, b13=b10
    """
    fen = int(round(yuan * 100))
    if not 0 <= fen <= 65535:
        raise ValueError("金额范围 0 ~ 655.35 元")
    if not 0 <= b4 <= 0xFF:
        raise ValueError("b4 范围 0x00 ~ 0xFF")
    block = bytearray(16)
    block[2:4] = fen.to_bytes(2, "little")
    block[4] = b4 & 0xFF
    block[1] = (block[2] + block[3] + block[4]) & 0xFF  # b1（b4 参与）
    block[5] = (~block[1]) & 0xFF                        # b5
    block[10] = counter & 0xFF                           # b10
    if used:
        block[11] = 0x01                                 # b11
        block[13] = (counter + 1) & 0xFF                 # b13
    else:
        block[11] = 0x00
        block[13] = counter & 0xFF
    x = 0
    for i in range(1, 15):
        x ^= block[i]
    block[0] = x                                         # b0
    block[15] = (~sum(block[1:15])) & 0xFF               # b15
    return bytes(block)


def _hex(text: str) -> int:
    return int(text.replace("0x", "").replace("0X", ""), 16)


while True:
    s = input("水控2 金额(元，q退出): ").strip()
    if s.lower() == "q":
        break
    try:
        yuan = float(s)
        b4_text = input("  b4 交易次数(回车默认 00): ").strip()
        b4 = _hex(b4_text) if b4_text else 0x00
        c = input("  计数器 b10(回车默认 FA): ").strip()
        counter = _hex(c) if c else 0xFA
        used_text = input("  机器写过的块? (Y/n, 回车默认 Y): ").strip().lower()
        used = used_text not in ("n", "no", "0", "false")
        blk = water2_block(yuan, b4, counter, used)
        fen = int(round(yuan * 100))
        print(f"  完整块: {blk.hex(' ').upper()}")
        print(f"  余额[2-3]: {blk[2:4].hex(' ').upper()}  ({fen}分, 小端)")
        print(f"  b4={blk[4]:02X}  b10={blk[10]:02X}  b11={blk[11]:02X}  b13={blk[13]:02X}")
        print(f"  校验: b0={blk[0]:02X}  b1={blk[1]:02X}  b5={blk[5]:02X}  b15={blk[15]:02X}")
        print("  → Block 16 / 18\n")
    except Exception as e:
        print(f"  错误: {e}\n")
