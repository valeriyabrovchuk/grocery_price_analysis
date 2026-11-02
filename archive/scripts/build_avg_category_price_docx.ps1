$ErrorActionPreference = 'Stop'

$root = Resolve-Path '.'
$outputDir = Join-Path $root 'output\doc'
$tmpRoot = Join-Path $root 'tmp\docs'
$docxPath = Join-Path $outputDir 'avg_price_difference_per_item_by_category_a4.docx'
$tmpDir = Join-Path $tmpRoot 'avg_price_docx_build'

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
New-Item -ItemType Directory -Force -Path $tmpRoot | Out-Null
if (Test-Path $tmpDir) {
    Remove-Item -LiteralPath $tmpDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $tmpDir '_rels') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $tmpDir 'word') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $tmpDir 'word\_rels') | Out-Null

$skPath = Join-Path $root 'output\avg_price_comparison_per_item_by_sklavenitis_category_v1.csv'
$amPath = Join-Path $root 'output\avg_price_comparison_per_item_by_alphamega_category_v1.csv'

$culture = [System.Globalization.CultureInfo]::InvariantCulture

$skRows = Import-Csv $skPath | Sort-Object -Property @{ Expression = { [double]::Parse($_.avg_diff_am_minus_sk_eur_per_item, $culture) }; Descending = $true }
$amRows = Import-Csv $amPath | Sort-Object -Property @{ Expression = { [double]::Parse($_.avg_diff_am_minus_sk_eur_per_item, $culture) }; Descending = $true }

function Escape-Xml([string]$text) {
    if ($null -eq $text) { return '' }
    return [System.Security.SecurityElement]::Escape($text)
}

function Signed-Euro([string]$value) {
    $number = [double]::Parse($value, $culture)
    if ($number -gt 0) { return ('+€' + $number.ToString('0.00', $culture)) }
    if ($number -lt 0) { return ('-€' + ([math]::Abs($number)).ToString('0.00', $culture)) }
    return '€0.00'
}

function Paragraph([string]$text, [string]$style = '', [int]$size = 18, [bool]$bold = $false) {
    $styleXml = ''
    if ($style) { $styleXml = "<w:pStyle w:val=`"$style`"/>" }
    $boldXml = ''
    if ($bold) { $boldXml = '<w:b/>' }
    $escaped = Escape-Xml $text
    return @"
<w:p>
  <w:pPr>$styleXml</w:pPr>
  <w:r>
    <w:rPr>$boldXml<w:sz w:val="$size"/><w:szCs w:val="$size"/></w:rPr>
    <w:t xml:space="preserve">$escaped</w:t>
  </w:r>
</w:p>
"@
}

function TableCell([string]$text, [int]$width, [bool]$bold = $false, [string]$shade = '', [string]$align = 'left') {
    $jc = if ($align -eq 'right') { '<w:jc w:val="right"/>' } elseif ($align -eq 'center') { '<w:jc w:val="center"/>' } else { '' }
    $boldXml = ''
    if ($bold) { $boldXml = '<w:b/>' }
    $shadeXml = ''
    if ($shade) { $shadeXml = "<w:shd w:fill=`"$shade`"/>" }
    $escaped = Escape-Xml $text
    return @"
<w:tc>
  <w:tcPr><w:tcW w:w="$width" w:type="dxa"/>$shadeXml</w:tcPr>
  <w:p>
    <w:pPr>$jc</w:pPr>
    <w:r>
      <w:rPr>$boldXml<w:sz w:val="14"/><w:szCs w:val="14"/></w:rPr>
      <w:t xml:space="preserve">$escaped</w:t>
    </w:r>
  </w:p>
</w:tc>
"@
}

function TableRow([string]$category, [string]$count, [string]$diff, [bool]$header = $false, [int]$index = 0) {
    $shade = ''
    if ($header) {
        $shade = 'D9EAF7'
    } elseif (($index % 2) -eq 0) {
        $shade = 'F6F8FA'
    }

    $categoryCell = TableCell $category 11600 $header $shade 'left'
    $countCell = TableCell $count 900 $header $shade 'right'
    $diffCell = TableCell $diff 1600 $header $shade 'right'
    return "<w:tr>$categoryCell$countCell$diffCell</w:tr>"
}

function DataTable($rows) {
    $xml = @()
    $xml += '<w:tbl>'
    $xml += '<w:tblPr><w:tblW w:w="14100" w:type="dxa"/><w:tblLayout w:type="fixed"/><w:tblBorders><w:top w:val="single" w:sz="4" w:color="B8C2CC"/><w:left w:val="single" w:sz="4" w:color="B8C2CC"/><w:bottom w:val="single" w:sz="4" w:color="B8C2CC"/><w:right w:val="single" w:sz="4" w:color="B8C2CC"/><w:insideH w:val="single" w:sz="3" w:color="D8DEE4"/><w:insideV w:val="single" w:sz="3" w:color="D8DEE4"/></w:tblBorders></w:tblPr>'
    $xml += '<w:tblGrid><w:gridCol w:w="11600"/><w:gridCol w:w="900"/><w:gridCol w:w="1600"/></w:tblGrid>'
    $xml += TableRow 'Категория' 'n' 'Разница' $true 0
    $i = 0
    foreach ($row in $rows) {
        $i += 1
        $xml += TableRow $row.category $row.matched_items (Signed-Euro $row.avg_diff_am_minus_sk_eur_per_item) $false $i
    }
    $xml += '</w:tbl>'
    return ($xml -join "`n")
}

$body = @()
$body += Paragraph 'Средняя разница цены на 1 matched товар' 'Title' 28 $true
$body += Paragraph '+ значит AlphaMega дороже. - значит Sklavenitis дороже. Цена = effective_price_eur: промо-цена, если она есть, иначе обычная цена.' '' 16 $false
$body += Paragraph ('Всего matched товаров: 841. Общая средняя разница: +€0.05 за 1 товар.') '' 16 $true
$body += Paragraph 'Категории Sklavenitis' 'Heading1' 22 $true
$body += DataTable $skRows
$body += Paragraph 'Категории AlphaMega' 'Heading1' 22 $true
$body += DataTable $amRows

$documentXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    $($body -join "`n")
    <w:sectPr>
      <w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>
      <w:pgMar w:top="454" w:right="454" w:bottom="454" w:left="454" w:header="0" w:footer="0" w:gutter="0"/>
      <w:cols w:space="708"/>
      <w:docGrid w:linePitch="360"/>
    </w:sectPr>
  </w:body>
</w:document>
"@

$stylesXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos" w:cs="Aptos"/><w:sz w:val="16"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:after="120"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="28"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="180" w:after="80"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="22"/></w:rPr>
  </w:style>
</w:styles>
"@

$contentTypesXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
"@

$relsXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"@

$documentRelsXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"@

$encoding = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $tmpDir '[Content_Types].xml'), $contentTypesXml, $encoding)
[System.IO.File]::WriteAllText((Join-Path $tmpDir '_rels\.rels'), $relsXml, $encoding)
[System.IO.File]::WriteAllText((Join-Path $tmpDir 'word\document.xml'), $documentXml, $encoding)
[System.IO.File]::WriteAllText((Join-Path $tmpDir 'word\styles.xml'), $stylesXml, $encoding)
[System.IO.File]::WriteAllText((Join-Path $tmpDir 'word\_rels\document.xml.rels'), $documentRelsXml, $encoding)

if (Test-Path $docxPath) {
    Remove-Item -LiteralPath $docxPath -Force
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($tmpDir, $docxPath)

Write-Output $docxPath
