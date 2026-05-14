# PowerShell: Export B站 cookies for Hermes scraper
# Usage: Close Chrome → Run this in PowerShell
yt-dlp --cookies-from-browser chrome --cookies "$env:USERPROFILE\Desktop\bili_cookies.txt"
Write-Host "=== Done ==="
if (Test-Path "$env:USERPROFILE\Desktop\bili_cookies.txt") {
    Write-Host "✅ Success! File saved to desktop as bili_cookies.txt"
    Write-Host "File size: $((Get-Item $env:USERPROFILE\Desktop\bili_cookies.txt).Length) bytes"
} else {
    Write-Host "❌ Failed. Try closing Chrome completely, or use Edge:"
    Write-Host "   yt-dlp --cookies-from-browser edge --cookies `"$env:USERPROFILE\Desktop\bili_cookies.txt`""
}
