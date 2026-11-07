# Web 读卡工具

只读工具：读取 TYYZ 水卡余额（消费钱包 / 水控1 / 水控2），并在需要时用 **hardnested** 破解 Sector 8 密钥后读取水控1。

## 文件

| 文件 | 作用 |
|---|---|
| `index.html` | 单文件网页（界面 + PN532 协议 + 解析） |
| `bridge.py` | 本地桥：网页调用它运行 `libnfc_hardnested.exe` 破解 S8 |

## 启动

```powershell
# 1) 关闭 PCR532 / PN532CardReader（释放 COM3）

# 2) 启动本地桥（保持窗口开着）
cd web
python bridge.py

# 3) 另开一个窗口启动网页服务
cd web
python -m http.server 8080
```

Chrome 打开 `http://localhost:8080`。

## 使用

1. **连接读卡器** → 选 `USB-SERIAL CH340 (COM3)`（会自动用 115200 / DTR=true / RTS=true）；
2. **读取卡片** → 直接读取 Sector 0–4（消费钱包、水控2），水控1 需要密钥；
3. 若要读水控1：
   - 点 **破解 S8/S9 并读取（较慢）**；
   - 网页会先读 UID、算出 Sector 1 密钥，释放串口；
   - 桥调用 `libnfc_hardnested.exe`，网页显示进度条（10~30 分钟，保持卡片贴在读卡器上）；
   - 成功后自动推导 S8B / S9A / S9B，重连读卡器并读取全部扇区。

## 密钥关系（自动推导）

```
S8 KeyB = S8 KeyA ^ 60 84 2D 00 00 0C
S9 KeyA = S8 KeyA ^ 00 01 20 00 00 04
S9 KeyB = S9 KeyA ^ 60 84 2D 00 00 0C
```

## 说明

- 浏览器必须是桌面 Chrome / Edge（Web Serial 限制）；
- 破解期间网页会关闭串口，否则 hardnested 打不开 COM3；
- 若桥提示工具缺失，检查 `C:\工具Tools\PCR532\nfc-bin\libnfc_hardnested.exe` 是否存在；
- 该工具依赖 `C:\工具Tools\PCR532\libnfc.conf`（`pn532_uart:COM3:115200`）。
