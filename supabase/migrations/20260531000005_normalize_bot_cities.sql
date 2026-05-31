UPDATE price_history SET city = 'Fort Sterling'  WHERE lower(replace(city,' ','')) = 'fortsterling'  AND city != 'Fort Sterling';
UPDATE price_history SET city = 'Brecilien'       WHERE lower(city) = 'brecilien'       AND city != 'Brecilien';
UPDATE price_history SET city = 'Bridgewatch'     WHERE lower(city) = 'bridgewatch'     AND city != 'Bridgewatch';
UPDATE price_history SET city = 'Caerleon'        WHERE lower(city) = 'caerleon'        AND city != 'Caerleon';
UPDATE price_history SET city = 'Lymhurst'        WHERE lower(city) = 'lymhurst'        AND city != 'Lymhurst';
UPDATE price_history SET city = 'Martlock'        WHERE lower(city) = 'martlock'        AND city != 'Martlock';
UPDATE price_history SET city = 'Thetford'        WHERE lower(city) = 'thetford'        AND city != 'Thetford';
DELETE FROM price_history WHERE city NOT IN ('Fort Sterling','Brecilien','Bridgewatch','Caerleon','Lymhurst','Martlock','Thetford');
