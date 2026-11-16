<#
.SYNOPSIS
  Equibase result-chart downloader (Doug's downloader, upgraded 2026-11-15).

.DESCRIPTION
  Reads jobs from a CSV (track,country,folder,date) and downloads each chart to
    <Root>\<folder>\<trk>-results-<year>\<yyyymmdd>-<country>-<trk>-a-d.standard.pdf

  The web request is Doug's, unchanged: plain Invoke-WebRequest -UseBasicParsing,
  no custom headers, no user-agent. Nothing here tries to get past a bot check.
  If Equibase blocks the client, the run STOPS:
    * after 3 HTTP 403 responses (in total), or
    * after 3 not-a-PDF responses in a row (the bot-check page comes back as
      HTTP 200 text/html, so it would never count as a 403).
  Other limits: a per-run request cap (default 1,500) and a random 4-8 s delay
  between requests. Skips (charts already on disk) are not requests and are
  not delayed.

  Already on disk = either naming style, anywhere under -Root:
    long : 20221101-usa-mnr-a-d.standard.pdf
    short: MNR110122USA.pdf  (also MNR110122USA8.pdf style suffixes)
  The index is built once at start, so a chart in an older folder layout
  (e.g. Mahoning Valley\mvr-2025-results) is not downloaded again. Get-Chart
  also keeps its own Test-Path check in the target folder.

  Optional jobs column: recheck (1 = ignore the on-disk index for that row; test
  batches only, with a separate folder).

  Log: CSV (timestamp,track,date,status,detail), appended. Status is
  ok / skip / none (404, no race day) / error / stop.

.EXAMPLE
  .\tools\chart_downloader.ps1 -JobsCsv .\scripts_dpv1\tracking\chart_archive\batch_00_test.csv
.EXAMPLE
  .\tools\chart_downloader.ps1 -JobsCsv ...\batch_01.csv -MaxRequests 800 -DryRun
#>
param(
    [Parameter(Mandatory = $true)][string]$JobsCsv,
    [string]$Root = 'D:\Benter Model_v2 Data\benter-model_v2-data',
    [int]$MaxRequests = 1500,
    [int]$MinDelaySec = 4,
    [int]$MaxDelaySec = 8,
    [string]$LogPath = '',
    [switch]$DryRun          # no requests: report what would be fetched / skipped
)

$ErrorActionPreference = 'Stop'
if (-not $LogPath) { $LogPath = Join-Path $Root ("chart_download_log_{0}.csv" -f (Get-Date -Format 'yyyyMMdd')) }

# ---------------------------------------------------------------- Get-Chart
# Doug's function. Only change: the country ("usa" before) comes from the job,
# for the URL path and the file names. The request itself is unchanged.
function Get-Chart([string]$Track, [datetime]$Day, [string]$Dir, [string]$Country = 'usa') {
    $T=$Track.ToUpper(); $t=$Track.ToLower(); $c=$Country.ToLower(); $C2=$Country.ToUpper()
    $long  = "{0}-{1}-{2}-a-d.standard.pdf" -f $Day.ToString('yyyyMMdd'), $c, $t
    $short = "{0}{1}{2}.pdf" -f $T, $Day.ToString('MMddyy'), $C2
    if ((Test-Path (Join-Path $Dir $long)) -or (Test-Path (Join-Path $Dir $short))) { return @('skip','already on disk') }
    $out = Join-Path $Dir $long
    $url = "https://www.equibase.com/static/chart/{0}/{1}/{2}/{3}" -f $Day.Year, $c, $t, $long
    try { Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
        $head = [System.Text.Encoding]::ASCII.GetString(([System.IO.File]::ReadAllBytes($out))[0..3])
        if ($head -ne '%PDF') { Remove-Item $out -EA SilentlyContinue; return @('error','not a PDF') }
        return @('ok', ('{0:N0} KB' -f ((Get-Item $out).Length / 1KB))) }
    catch { Remove-Item $out -EA SilentlyContinue; $code=$null
        try { $code = [int]$_.Exception.Response.StatusCode } catch {}
        if ($code -eq 404) { return @('none','no chart (404)') }
        if ($code -eq 403) { return @('error','HTTP 403') }
        return @('error', $(if ($code) { "HTTP $code" } else { $_.Exception.Message })) }
}

# ---------------------------------------------------------------- helpers
function Write-Log([string]$Track, [string]$Date, [string]$Status, [string]$Detail) {
    if (-not (Test-Path $LogPath)) { 'timestamp,track,date,status,detail' | Out-File -FilePath $LogPath -Encoding ascii }
    $d = $Detail -replace '"', "'"
    ('{0},{1},{2},{3},"{4}"' -f (Get-Date -Format 's'), $Track, $Date, $Status, $d) | Out-File -FilePath $LogPath -Append -Encoding ascii
}

# Index of charts already on disk, both naming styles: key = "TRK|yyyyMMdd"
function Get-ChartIndex([string]$Base) {
    $idx = @{}
    $reLong  = '^(\d{8})-(usa|can)-([a-z]+)-a-d\.standard\.pdf$'
    $reShort = '^([A-Za-z]+?)(\d{2})(\d{2})(\d{2})(USA|CAN)\d?\.pdf$'
    Get-ChildItem -Path $Base -Recurse -File -Filter *.pdf -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\_bad_charts\\' } | ForEach-Object {
            $n = $_.Name
            if ($n -match $reLong) { $idx[("{0}|{1}" -f $Matches[3].ToUpper(), $Matches[1])] = $_.FullName }
            elseif ($n -match $reShort) { $idx[("{0}|20{1}{2}{3}" -f $Matches[1].ToUpper(), $Matches[4], $Matches[2], $Matches[3])] = $_.FullName }
        }
    return $idx
}

# ---------------------------------------------------------------- jobs
$jobs = @(Import-Csv -Path $JobsCsv)
foreach ($col in 'track', 'country', 'folder', 'date') {
    if ($jobs.Count -gt 0 -and -not ($jobs[0].PSObject.Properties.Name -contains $col)) { throw "Jobs CSV is missing column '$col'" }
}
Write-Host ("Jobs: {0} from {1}" -f $jobs.Count, $JobsCsv)
Write-Host "Indexing charts already on disk under $Root ..."
$index = Get-ChartIndex $Root
Write-Host ("  {0} charts on disk" -f $index.Count)
if ($DryRun) { Write-Host 'DRY RUN: no requests will be made, nothing is logged.' }

$stats = @{ ok = 0; skip = 0; none = 0; error = 0 }
$perTrack = [ordered]@{}
$requests = 0; $n403 = 0; $notPdfRun = 0; $stopReason = ''
$rand = New-Object System.Random

foreach ($j in $jobs) {
    $trk = $j.track.Trim().ToUpper()
    $ctry = if ($j.country -and $j.country.Trim()) { $j.country.Trim().ToLower() } else { 'usa' }
    $day = [datetime]::ParseExact($j.date.Trim(), 'yyyy-MM-dd', $null)
    $dstr = $day.ToString('yyyy-MM-dd')
    $dir = Join-Path (Join-Path $Root $j.folder.Trim()) ("{0}-results-{1}" -f $trk.ToLower(), $day.Year)
    if (-not $perTrack.Contains($trk)) { $perTrack[$trk] = @{ ok = 0; skip = 0; none = 0; error = 0 } }

    # already on disk anywhere under Root (either naming style) -> skip, no request.
    # Optional column recheck=1 (test batches only): ignore the index, so a chart we
    # hold under the short name can be re-fetched from the long-name address. Use a
    # separate folder for those rows (Get-Chart still skips if it is already there).
    $key = "{0}|{1}" -f $trk, $day.ToString('yyyyMMdd')
    $recheck = ($j.PSObject.Properties.Name -contains 'recheck') -and ("$($j.recheck)".Trim() -eq '1')
    if (-not $recheck -and $index.ContainsKey($key)) {
        $stats.skip++; $perTrack[$trk].skip++
        if (-not $DryRun) { Write-Log $trk $dstr 'skip' 'already on disk' }
        continue
    }
    if ($requests -ge $MaxRequests) { $stopReason = "request cap reached ($MaxRequests)"; break }

    if ($DryRun) {
        $requests++
        Write-Host ("  would fetch {0} {1} ({2}) -> {3}" -f $trk, $dstr, $ctry, $dir)
        continue
    }

    if ($requests -gt 0) { Start-Sleep -Milliseconds ($rand.Next($MinDelaySec * 1000, $MaxDelaySec * 1000 + 1)) }
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $requests++
    $r = Get-Chart -Track $trk -Day $day -Dir $dir -Country $ctry
    $status = $r[0]; $detail = $r[1]
    $stats[$status]++; $perTrack[$trk][$status]++
    Write-Log $trk $dstr $status $detail
    Write-Host ("  {0} {1} {2}: {3}" -f $trk, $dstr, $status, $detail)

    if ($status -eq 'ok') { $index[$key] = 'downloaded' }
    if ($detail -eq 'HTTP 403') { $n403++ }
    if ($detail -eq 'not a PDF') { $notPdfRun++ } else { $notPdfRun = 0 }
    if ($n403 -ge 3) { $stopReason = '3 HTTP 403 responses'; break }
    if ($notPdfRun -ge 3) { $stopReason = '3 not-a-PDF responses in a row (likely the bot-check page)'; break }
}

# ---------------------------------------------------------------- summary
Write-Host ''
Write-Host 'Per track:'
foreach ($k in $perTrack.Keys) {
    $p = $perTrack[$k]
    Write-Host ("  {0,-5} Downloaded: {1,4}   Already had: {2,4}   No race day: {3,4}   Errors: {4,3}" -f $k, $p.ok, $p.skip, $p.none, $p.error)
}
Write-Host ''
if ($stopReason) {
    Write-Host "STOPPED: $stopReason" -ForegroundColor Yellow
    if (-not $DryRun) { Write-Log '' '' 'stop' $stopReason }
}
Write-Host ("Requests: {0}{1}" -f $requests, $(if ($DryRun) { ' (dry run, none sent)' } else { '' }))
Write-Host ("Downloaded: {0}   Already had: {1}   No race day: {2}   Errors: {3}" -f $stats.ok, $stats.skip, $stats.none, $stats.error)
if (-not $DryRun) { Write-Host "Log: $LogPath" }
