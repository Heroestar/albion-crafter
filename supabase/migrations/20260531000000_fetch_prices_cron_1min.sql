-- Update fetch-prices cron from hourly to every minute
select cron.unschedule('fetch-prices-hourly')
where exists (
  select 1 from cron.job where jobname = 'fetch-prices-hourly'
);

select cron.schedule(
  'fetch-prices-every-minute',
  '* * * * *',
  $$
  select net.http_post(
    url     := 'https://huhpjepvqfkuezxmxnuw.supabase.co/functions/v1/fetch-prices',
    headers := '{"Content-Type":"application/json","Authorization":"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1aHBqZXB2cWZrdWV6eG14bnV3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkxMTE5MzUsImV4cCI6MjA5NDY4NzkzNX0.ql9Zzbrj4ohh_jsrt1KHxP5XK8_SEMyMW3XGNx4WtvQ"}'::jsonb,
    body    := '{}'::jsonb
  );
  $$
);
