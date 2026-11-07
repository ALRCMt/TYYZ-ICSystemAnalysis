# TYYZ 读卡（安卓 · 手机 NFC · 只读）

用手机自带的 NFC 读取校园卡信息，不写卡。

- 界面就是仓库里的 `web/index.html`（只读版），构建时自动复制到 `app/src/main/assets/`；
- 手机 NFC 读取的数据块通过 JS 桥 `window.AndroidNfc` 回传给网页，解析/展示/Dump 编辑全部复用网页逻辑。

## 环境要求

- Android Studio（或命令行 Gradle 8.x + JDK 17）；
- 手机 NFC 芯片需支持 MIFARE Classic（NXP 系大多支持，部分机型不支持，App 会提示）；
- 手机系统 Android 5.0+（minSdk 21）。

## 构建

### 方式一：Android Studio（推荐）

1. 打开 Android Studio → **Open**，选择本 `android/` 目录；
2. 等待 Gradle 同步（首次会自动下载 AGP/Kotlin）；
3. 连接手机（开启 USB 调试）→ 点 **Run**；
4. 或 **Build → Build Bundle(s)/APK(s) → Build APK(s)**，生成 `app/build/outputs/apk/debug/app-debug.apk`。

> 如果提示缺少 Gradle Wrapper，在 Android Studio 里让它使用自带的 Gradle
> （Settings → Build, Execution, Deployment → Build Tools → Gradle → Use Gradle from: 'gradle-wrapper.properties' 或本地 Gradle），
> 或在 `android/` 下执行一次 `gradle wrapper`。

### 方式二：命令行

```bash
cd android
gradle assembleDebug
```

## 使用

1. 打开 App（确保手机 NFC 已开启）；
2. 需要读水控1 时，在「水控1 密钥」里填 S8 或 S9 的 KeyA（12 位 hex，填一个即可）；
3. 点 **「手机 NFC 读卡」**，把卡片贴到手机 NFC 感应区；
4. 网页会显示结果：UID、卡号/姓名/开卡日期、消费钱包、水控2、水控1。

## 实现说明

| 文件 | 作用 |
|---|---|
| `app/src/main/java/top/tyyz2415/cardreader/MainActivity.kt` | WebView 壳 + NFC Reader Mode + JS 桥 |
| `app/src/main/java/top/tyyz2415/cardreader/NfcReader.kt` | `MifareClassic` 认证与读块，返回 JSON |
| `app/src/main/java/top/tyyz2415/cardreader/Keys.kt` | UID → S1-3/S4 密钥推导 |
| `app/build.gradle.kts` | 构建前把 `../web/index.html` 同步到 assets |

读取范围：

- Block 0（UID/厂商块，免认证，失败则用 `FF…FF` 重试）；
- Sector 1–3：UID 推导 KeyA；
- Sector 4：UID 推导 KeyA；
- Sector 8/9：需用户输入 KeyA，认证失败再试 KeyB（可用于读被"锁"的扇区）。

**不包含任何写卡代码**（没有 `writeBlock`、没有尾块/S0 写入）。

## 已知限制

- 手机 NFC 不支持 M1 的机型无法使用（`MifareClassic.get(tag)` 返回 null）；
- 被访问位锁定为"只能 KeyB"的扇区，需要填 KeyB 才能读；
- 网页端原有的串口读卡（PN532）仍保留在桌面浏览器里，App 内自动显示「手机 NFC 读卡」按钮。
