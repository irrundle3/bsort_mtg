SELECT
    set_code,
    AVG(price) AS avg_price,
    date_priced
FROM public.price_details
WHERE currency = 'USD'
    AND set_code IN ('3ED')
GROUP BY date_priced, set_code;