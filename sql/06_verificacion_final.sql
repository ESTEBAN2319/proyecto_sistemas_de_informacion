/*
    Fase 2. Verificación final del almacén cargado.

    Abrir en SQL Server Management Studio como consulta nueva
    y ejecutar completo (F5) contra localhost\SQLEXPRESS.

    No depende de la base seleccionada en la barra: usa nombres de tres partes.
    Cada fila debe decir OK. Una sola FALLO invalida el almacén.

    No ejecutar sql/03_verificar_dwh_vacio.sql: ese script correspondía al
    esquema vacío, antes de la carga.
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
        'Resto sin coste y sin margen',
        CAST(64 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks_DWH.dbo.Fact_Sales
            WHERE Channel = 'Resto'
              AND UnitCost IS NULL
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
        'Productos',
        CAST(504 AS decimal(19, 4)),
        CAST((SELECT COUNT(*) FROM AdventureWorks_DWH.dbo.Dim_Product) AS decimal(19, 4))

    UNION ALL
    SELECT
        'Territorios',
        CAST(10 AS decimal(19, 4)),
        CAST((SELECT COUNT(*) FROM AdventureWorks_DWH.dbo.Dim_Territory) AS decimal(19, 4))

    UNION ALL
    SELECT
        'Fechas fiscales mal asignadas',
        CAST(0 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks_DWH.dbo.Dim_Date
            WHERE (Month >= 7 AND FiscalYear <> CalendarYear + 1)
               OR (Month <= 6 AND FiscalYear <> CalendarYear)
        ) AS decimal(19, 4))

    UNION ALL
    SELECT
        'OLTP intacto',
        CAST(121317 AS decimal(19, 4)),
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks2025.Sales.SalesOrderDetail
        ) AS decimal(19, 4))
) AS pruebas
ORDER BY Resultado, Prueba;
GO
