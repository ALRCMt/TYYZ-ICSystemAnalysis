def water2_block(yuan: float, counter: int = 0xFA) -> bytes:
    fen = int(round(yuan * 100))
    if not 0 <= fen <= 65535:
        raise ValueError("金额范围 0 ~ 655.35 元")
    block = bytearray(16)
    block[2:4] = fen.to_bytes(2, "little")
    lo, hi = fen & 0xFF, (fen >> 8) & 0xFF
    block[1] = (lo + hi) & 0xFF
    block[5] = (~block[1]) & 0xFF
    block[11] = 0x01
    block[10] = counter & 0xFF
    block[13] = (counter + 1) & 0xFF
    x = 0
    for i in range(1, 15):
        x ^= block[i]
    block[0] = x
    block[15] = (~sum(block[1:15]) & 0xFF)
    return bytes(block)


while True:
    s = input("水控2 金额(元，q退出): ").strip()
    if s.lower() == "q":
        break
    try:
        yuan = float(s)
        c = input("  计数器b10(回车默认FA): ").strip()
        counter = int(c, 16) if c else 0xFA
        blk = water2_block(yuan, counter)
        fen = int(round(yuan * 100))
        print(f"  完整块: {blk.hex(' ').upper()}")
        print(f"  余额[2-3]: {blk[2:4].hex(' ').upper()}  ({fen}分, 小端)")
        print(f"  校验: b0={blk[0]:02X}  b1={blk[1]:02X}  b5={blk[5]:02X}  b15={blk[15]:02X}")
        print(f"  → Block 16 / 18\n")
    except Exception as e:
        print(f"  错误: {e}\n")