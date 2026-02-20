# Set Vercel environment variables
$envVars = @{
    "SUPABASE_URL" = "https://wmsyvahmriucdyykpuau.supabase.co"
    "SUPABASE_SERVICE_KEY" = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indtc3l2YWhtcml1Y2R5eWtwdWF1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTU1MzY0MiwiZXhwIjoyMDg3MTI5NjQyfQ.07mnOGyicHSbDuBjPXBvxtzHkKRqxvJd1TPbCwFnDnA"
    "JWT_SECRET" = "moLfQBd1iQ1NtA84/liOWuFekSHrVsk+4pbRTJSB2DpG3KxTUMK+UKfQCdHL4/vVW9A1lt0UhYRKagJKATJFXQ=="
    "EMERGENT_LLM_KEY" = "sk-emergent-9C75d369a647a1f805"
}

foreach ($key in $envVars.Keys) {
    Write-Host "Setting $key..."
    $envVars[$key] | vercel env add $key production --force 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Trying without --force..."
        $envVars[$key] | vercel env add $key production 2>&1
    }
    Write-Host "  Done: $key"
}

Write-Host "`nAll environment variables set!"
