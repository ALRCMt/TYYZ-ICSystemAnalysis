function Get-Water2Block {
    param(
        [double]$Yuan,
        [int]$Counter = 0xFA
    )

    $fen = [int][Math]::Round($Yuan * 100, [MidpointRounding]::ToEven)
    if ($fen -lt 0 -or $fen -gt 65535) {
        throw "金额范围 0 ~ 655.35 元"
    }

    $block = New-Object byte[] 16
    $block[2] = [byte]($fen -band 0xFF)
    $block[3] = [byte](($fen -shr 8) -band 0xFF)
    $lo = [int]$block[2]
    $hi = [int]$block[3]
    $block[1] = [byte](($lo + $hi) -band 0xFF)
    $block[5] = [byte]($block[1] -bxor 0xFF)
    $block[11] = 0x01
    $block[10] = [byte]($Counter -band 0xFF)
    $block[13] = [byte](($Counter + 1) -band 0xFF)

    $x = 0
    for ($i = 1; $i -lt 15; $i++) {
        $x = $x -bxor $block[$i]
    }
    $block[0] = [byte]$x

    $sum = 0
    for ($i = 1; $i -lt 15; $i++) {
        $sum += [int]$block[$i]
    }
    $block[15] = [byte]((-$sum) -band 0xFF)

    return ,$block
}

function Format-HexBytes {
    param([byte[]]$Bytes)

    return (($Bytes | ForEach-Object { $_.ToString("X2") }) -join " ")
}

while ($true) {
    $s = (Read-Host "水控2 金额(元，q退出)").Trim()
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

        $counterText = (Read-Host "  计数器b10(回车默认FA)").Trim()
        if ($counterText) {
            $counterText = $counterText -replace "^0[xX]", ""
            $counter = [Convert]::ToInt32($counterText, 16)
        }
        else {
            $counter = 0xFA
        }

        $blk = Get-Water2Block -Yuan $yuan -Counter $counter
        $fen = [int][Math]::Round($yuan * 100, [MidpointRounding]::ToEven)
        Write-Host "  完整块: $(Format-HexBytes -Bytes $blk)"
        Write-Host "  余额[2-3]: $(Format-HexBytes -Bytes $blk[2..3])  (${fen}分, 小端)"
        Write-Host "  校验: b0=$('{0:X2}' -f $blk[0])  b1=$('{0:X2}' -f $blk[1])  b5=$('{0:X2}' -f $blk[5])  b15=$('{0:X2}' -f $blk[15])"
        Write-Host "  → Block 16 / 18`n"
    }
    catch {
        Write-Host "  错误: $($_.Exception.Message)`n"
    }
}
