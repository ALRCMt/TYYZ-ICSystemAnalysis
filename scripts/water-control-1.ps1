function Get-Water1Block {
    param([double]$Yuan)

    $fen = [int][Math]::Round($Yuan * 100, [MidpointRounding]::ToEven)
    if ($fen -lt 0 -or $fen -gt 65535) {
        throw "金额范围 0 ~ 655.35 元"
    }

    $block = New-Object byte[] 16
    $block[0] = 0x10
    $block[1] = 0xAC
    $block[2] = 0x0C
    $block[3] = 0xAF
    $block[4] = [byte](($fen -shr 8) -band 0xFF)
    $block[5] = [byte]($fen -band 0xFF)

    $crc = 0
    foreach ($b in @($block[4], $block[5])) {
        $crc = $crc -bxor ([int]$b -shl 8)
        for ($i = 0; $i -lt 8; $i++) {
            if (($crc -band 0x8000) -ne 0) {
                $crc = (($crc -shl 1) -bxor 0x1021) -band 0xFFFF
            }
            else {
                $crc = ($crc -shl 1) -band 0xFFFF
            }
        }
    }
    $crc = $crc -bxor 0x20F5
    $block[6] = [byte](($crc -shr 8) -band 0xFF)
    $block[7] = [byte]($crc -band 0xFF)

    return ,$block
}

function Format-HexBytes {
    param([byte[]]$Bytes)

    return (($Bytes | ForEach-Object { $_.ToString("X2") }) -join " ")
}

while ($true) {
    $s = (Read-Host "水控1 金额(元，q退出)").Trim()
    if ($s.ToLowerInvariant() -eq "q") {
        break
    }

    try {
        $yuan = 0.0
        if (-not [double]::TryParse(
                $s,
                [Globalization.NumberStyles]::Float,
                [Globalization.CultureInfo]::InvariantCulture,
                [ref]$yuan
            )) {
            throw "金额格式无效"
        }
        if ([double]::IsNaN($yuan) -or [double]::IsInfinity($yuan)) {
            throw "金额必须是有限数值"
        }

        $blk = Get-Water1Block -Yuan $yuan
        $fen = [int][Math]::Round($yuan * 100, [MidpointRounding]::ToEven)
        Write-Host "  完整块: $(Format-HexBytes -Bytes $blk)"
        Write-Host "  余额[4-5]: $(Format-HexBytes -Bytes $blk[4..5])  (${fen}分, 大端)"
        Write-Host "  校验[6-7]: $(Format-HexBytes -Bytes $blk[6..7])  (CRC16 XOR 0x20F5)"
        Write-Host "  → Block 37 / 38`n"
    }
    catch {
        Write-Host "  错误: $($_.Exception.Message)`n"
    }
}
