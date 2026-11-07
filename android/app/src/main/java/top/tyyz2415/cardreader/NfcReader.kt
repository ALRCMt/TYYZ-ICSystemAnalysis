package top.tyyz2415.cardreader

import android.nfc.Tag
import android.nfc.tech.MifareClassic
import org.json.JSONArray
import org.json.JSONObject

/**
 * 只读读卡器：使用手机自带 NFC 的 MifareClassic API。
 *
 * 只读取数据块（0-2），不修改卡片：
 *  - Sector 0 block 0：UID / 厂商块
 *  - Sector 1-3：UID 推导密钥（KeyA）
 *  - Sector 4：UID 推导密钥（KeyA）
 *  - Sector 8/9：使用调用方传入的 KeyA，失败再试 KeyB
 */
class NfcReader {

    fun read(tag: Tag, k8: ByteArray?, k9: ByteArray?): String {
        val result = JSONObject()
        val blocks = JSONObject()
        val errors = JSONArray()
        var mc: MifareClassic? = null

        try {
            mc = MifareClassic.get(tag)
            if (mc == null) {
                return errorJson("不是 MIFARE Classic 卡，或手机 NFC 芯片不支持 M1")
            }
            mc.connect()

            val uid = mc.tag.id
            if (uid == null || uid.size < 4) {
                return errorJson("读取 UID 失败")
            }

            val k123 = Keys.deriveS123(uid)
            val k4 = Keys.deriveS4A(uid)

            // Block 0 一般免认证可读；失败则用默认密钥认证后重试
            if (!readBlock(mc, 0, blocks, errors)) {
                if (auth(mc, 0, Keys.DEFAULT_KEY, null)) {
                    readBlock(mc, 0, blocks, errors)
                }
            }

            // Sector 1-3
            for (s in 1..3) {
                if (auth(mc, s, k123, null)) {
                    readDataBlocks(mc, s, blocks, errors)
                } else {
                    errors.put("S$s 认证失败（KeyA）")
                }
            }

            // Sector 4
            if (auth(mc, 4, k4, null)) {
                readDataBlocks(mc, 4, blocks, errors)
            } else {
                errors.put("S4 认证失败（KeyA）")
            }

            // Sector 8/9：需要外部提供密钥
            val extras = listOf(8 to k8, 9 to k9)
            for ((sector, key) in extras) {
                if (key == null || key.size != 6) {
                    errors.put("S$sector 未提供密钥，跳过")
                    continue
                }
                if (auth(mc, sector, key, key)) {
                    readDataBlocks(mc, sector, blocks, errors)
                } else {
                    errors.put("S$sector 认证失败（KeyA/KeyB）")
                }
            }

            result.put("uid", Keys.toHex(uid))
            result.put("blocks", blocks)
            result.put("errors", errors)
            result.put("readCount", blocks.length())
            return result.toString()
        } catch (e: Exception) {
            return errorJson("读卡异常：" + (e.message ?: e.toString()))
        } finally {
            try {
                mc?.close()
            } catch (_: Exception) {
            }
        }
    }

    private fun auth(mc: MifareClassic, sector: Int, keyA: ByteArray?, keyB: ByteArray?): Boolean {
        try {
            if (keyA != null && mc.authenticateSectorWithKeyA(sector, keyA)) return true
        } catch (_: Exception) {
        }
        try {
            if (keyB != null && mc.authenticateSectorWithKeyB(sector, keyB)) return true
        } catch (_: Exception) {
        }
        return false
    }

    private fun readDataBlocks(mc: MifareClassic, sector: Int, blocks: JSONObject, errors: JSONArray) {
        for (i in 0..2) {
            readBlock(mc, sector * 4 + i, blocks, errors)
        }
    }

    private fun readBlock(mc: MifareClassic, block: Int, blocks: JSONObject, errors: JSONArray): Boolean {
        return try {
            val data = mc.readBlock(block)
            if (data != null && data.size == 16) {
                blocks.put(block.toString(), Keys.toHex(data))
                true
            } else {
                errors.put("块 $block 数据长度异常")
                false
            }
        } catch (e: Exception) {
            errors.put("块 $block 读取失败")
            false
        }
    }

    private fun errorJson(message: String): String {
        val obj = JSONObject()
        obj.put("error", message)
        return obj.toString()
    }
}
