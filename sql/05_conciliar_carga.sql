/*
    Fase 2. Conciliación después del ETL.

    Cada fila debe decir OK. Una sola FALLO invalida la carga.
    El canal vive en Fact_Sales. No se vuelve a unir el OLTP para filtrar internet.
    El tipo de cliente es Store si hay StoreID; si no, Person.
*/
SELECT
    Prueba,
    Esperado,
    Obtenido,
    CASE WHEN Esperado = Obtenido THEN 'OK' ELSE 'FALLO' END AS Resultado
FROM (
    SELECT
        'Lineas OLTP' AS Prueba,
        CAST(121317 AS decimal(19, 4)) AS Esperado,
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks2025.Sales.SalesOrderDetail
        ) AS decimal(19, 4)) AS Obtenido

    UNION ALL
    SELECT
        'Lineas Fact_Sales',
        CAST(121317 AS decimal(19, 4)),
        CAST((SELECT COUNT(*) FROM AdventureWorks_DWH.dbo.Fact_Sales) AS decimal(19, 4))

    UNION ALL
    SELECT
        'Lineas unicas SalesOrderDetailID',
        CAST(121317 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(DISTINCT SalesOrderDetailID)
            FROM AdventureWorks_DWH.dbo.Fact_Sales
        ) AS decimal(19, 4))

    UNION ALL
    SELECT
        'Importe origen',
        CAST(109846381.4250 AS decimal(19, 4)),
        (
            SELECT SUM(CAST(LineTotal AS decimal(19, 4)))
            FROM AdventureWorks2025.Sales.SalesOrderDetail
        )

    UNION ALL
    SELECT
        'Importe Fact_Sales',
        CAST(109846381.4250 AS decimal(19, 4)),
        (SELECT SUM(SalesAmount) FROM AdventureWorks_DWH.dbo.Fact_Sales)

    UNION ALL
    SELECT
        'Lineas Internet',
        CAST(60398 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks_DWH.dbo.Fact_Sales
            WHERE Channel = 'Internet'
        ) AS decimal(19, 4))

    UNION ALL
    SELECT
        'Importe Internet',
        CAST(29358677.2207 AS decimal(19, 4)),
        (
            SELECT SUM(SalesAmount)
            FROM AdventureWorks_DWH.dbo.Fact_Sales
            WHERE Channel = 'Internet'
        )

    UNION ALL
    SELECT
        'Internet sin coste',
        CAST(0 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks_DWH.dbo.Fact_Sales
            WHERE Channel = 'Internet'
              AND UnitCost IS NULL
        ) AS decimal(19, 4))

    UNION ALL
    SELECT
        'Lineas Resto',
        CAST(60919 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks_DWH.dbo.Fact_Sales
            WHERE Channel = 'Resto'
        ) AS decimal(19, 4))

    UNION ALL
    SELECT
        'Importe Resto',
        CAST(80487704.2043 AS decimal(19, 4)),
        (
            SELECT SUM(SalesAmount)
            FROM AdventureWorks_DWH.dbo.Fact_Sales
            WHERE Channel = 'Resto'
        )

    UNION ALL
    SELECT
        'Resto sin coste',
        CAST(64 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks_DWH.dbo.Fact_Sales
            WHERE Channel = 'Resto'
              AND UnitCost IS NULL
        ) AS decimal(19, 4))

    UNION ALL
    SELECT
        'Resto sin margen',
        CAST(64 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks_DWH.dbo.Fact_Sales
            WHERE Channel = 'Resto'
              AND Margin IS NULL
        ) AS decimal(19, 4))

    UNION ALL
    SELECT
        'Coste y margen vacios juntos',
        CAST(64 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks_DWH.dbo.Fact_Sales
            WHERE UnitCost IS NULL
              AND LineCost IS NULL
              AND Margin IS NULL
        ) AS decimal(19, 4))

    UNION ALL
    SELECT
        'Clientes persona',
        CAST(18484 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks_DWH.dbo.Dim_Customer
            WHERE CustomerType = 'Person'
        ) AS decimal(19, 4))

    UNION ALL
    SELECT
        'Clientes tienda',
        CAST(1336 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks_DWH.dbo.Dim_Customer
            WHERE CustomerType = 'Store'
        ) AS decimal(19, 4))

    UNION ALL
    SELECT
        'Canal no se deduce del cliente',
        CAST(0 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks_DWH.dbo.Fact_Sales AS f
            INNER JOIN AdventureWorks_DWH.dbo.Dim_Customer AS c
                ON c.CustomerKey = f.CustomerKey
            WHERE f.Channel = 'Internet'
              AND c.CustomerType = 'Store'
        ) AS decimal(19, 4))

    UNION ALL
    SELECT
        'Flete e impuesto fuera del hecho',
        CAST(0 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks_DWH.sys.columns
            WHERE object_id = OBJECT_ID(N'AdventureWorks_DWH.dbo.Fact_Sales')
              AND name IN ('Freight', 'TaxAmt', 'Tax')
        ) AS decimal(19, 4))
) AS pruebas
ORDER BY Resultado, Prueba;
GO
