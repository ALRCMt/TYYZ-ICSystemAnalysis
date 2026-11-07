def water1_block(yuan: float) -> bytes:
    fen = int(round(yuan * 100))
    if not 0 <= fen <= 65535:
        raise ValueError("金额范围 0 ~ 655.35 元")
    bal = fen.to_bytes(2, "big")
    crc, poly = 0x0000, 0x1021
    for b in bal:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    crc ^= 0x20F5
    return bytes.fromhex("10AC0CAF") + bal + crc.to_bytes(2, "big") + bytes(8)


while True:
    s = input("水控1 金额(元，q退出): ").strip()
    if s.lower() == "q":
        break
    try:
        yuan = float(s)
        blk = water1_block(yuan)
        fen = int(round(yuan * 100))
        print(f"  完整块: {blk.hex(' ').upper()}")
        print(f"  余额[4-5]: {blk[4:6].hex(' ').upper()}  ({fen}分, 大端)")
        print(f"  校验[6-7]: {blk[6:8].hex(' ').upper()}  (CRC16 XOR 0x20F5)")
        print(f"  → Block 37 / 38\n")
    except Exception as e:
        print(f"  错误: {e}\n")