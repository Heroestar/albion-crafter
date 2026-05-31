-- Re-normalize any city names inserted after the first normalization migration
UPDATE price_history SET city = 'Fort Sterling'   WHERE city ILIKE 'fort sterling'   AND city != 'Fort Sterling';
UPDATE price_history SET city = 'Brecilien'        WHERE city ILIKE 'brecilien'        AND city != 'Brecilien';
UPDATE price_history SET city = 'Bridgewatch'      WHERE city ILIKE 'bridgewatch'      AND city != 'Bridgewatch';
UPDATE price_history SET city = 'Caerleon'         WHERE city ILIKE 'caerleon'         AND city != 'Caerleon';
UPDATE price_history SET city = 'Lymhurst'         WHERE city ILIKE 'lymhurst'         AND city != 'Lymhurst';
UPDATE price_history SET city = 'Martlock'         WHERE city ILIKE 'martlock'         AND city != 'Martlock';
UPDATE price_history SET city = 'Thetford'         WHERE city ILIKE 'thetford'         AND city != 'Thetford';
UPDATE price_history SET city = 'Fort Sterling'    WHERE lower(replace(city,' ','')) = 'fortsterling' AND city != 'Fort Sterling';

DELETE FROM price_history
WHERE city NOT IN ('Fort Sterling','Brecilien','Bridgewatch','Caerleon','Lymhurst','Martlock','Thetford');
