-- Remove AODP API cron jobs, bot data only from here
select cron.unschedule('fetch-prices-every-minute')
where exists (select 1 from cron.job where jobname = 'fetch-prices-every-minute');

select cron.unschedule('fetch-prices-hourly')
where exists (select 1 from cron.job where jobname = 'fetch-prices-hourly');
