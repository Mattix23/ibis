SELECT sum(`d`) OVER (ORDER BY `f` ASC RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS `foo`
FROM alltypes