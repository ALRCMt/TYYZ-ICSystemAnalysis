package top.tyyz2415.cardreader

/** 密钥推导与工具函数（与 web/index.html 中的实现保持一致） */
object Keys {

    val DEFAULT_KEY: ByteArray = byteArrayOf(
        0xFF.toByte(), 0xFF.toByte(), 0xFF.toByte(),
        0xFF.toByte(), 0xFF.toByte(), 0xFF.toByte()
    )

    /** Sector 1-3 KeyA（= KeyB）= f(UID) */
    fun deriveS123(uid: ByteArray): ByteArray {
        require(uid.size >= 4) { "UID 至少 4 字节" }
        val u0 = uid[0].toInt() and 0xFF
        val u1 = uid[1].toInt() and 0xFF
        val u2 = uid[2].toInt() and 0xFF
        val u3 = uid[3].toInt() and 0xFF
        return byteArrayOf(
            (u1 xor 0x1B).toByte(),
            (u3 xor 0x93).toByte(),
            (u2 xor 0x24).toByte(),
            (u3 xor 0xEA).toByte(),
            (u1 xor 0x26).toByte(),
            (u0 xor 0x89).toByte()
        )
    }

    /** Sector 4 KeyA = 04 || ~UID || 81 */
    fun deriveS4A(uid: ByteArray): ByteArray {
        require(uid.size >= 4) { "UID 至少 4 字节" }
        return byteArrayOf(
            0x04,
            (uid[0].toInt() xor 0xFF).toByte(),
            (uid[1].toInt() xor 0xFF).toByte(),
            (uid[2].toInt() xor 0xFF).toByte(),
            (uid[3].toInt() xor 0xFF).toByte(),
            0x81.toByte()
        )
    }

    fun toHex(data: ByteArray): String =
        data.joinToString("") { "%02X".format(it.toInt() and 0xFF) }
}
