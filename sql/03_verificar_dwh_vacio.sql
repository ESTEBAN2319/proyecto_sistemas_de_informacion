/*
    Fase 1. Confirma que el almacén está vacío y que el hecho ya tiene
    canal, coste unitario, coste de línea y margen.

    Cada fila debe decir OK. Una sola FALLO invalida el modelo.
    Ejecutar después de sql/02_crear_esquema_estrella.sql.
    No carga datos y no toca AdventureWorks2025.
*/
USE AdventureWorks_DWH;
GO

SELECT
    Prueba,
    Esperado,
    Obtenido,
    CASE WHEN Esperado = Obtenido THEN 'OK' ELSE 'FALLO' END AS Resultado
FROM (
    SELECT
        'Tablas del modelo' AS Prueba,
        '5' AS Esperado,
        CAST((
            SELECT COUNT(*)
            FROM sys.tables
            WHERE name IN (
                'Dim_Date', 'Dim_Product', 'Dim_Customer', 'Dim_Territory', 'Fact_Sales'
            )
        ) AS varchar(20)) AS Obtenido

    UNION ALL
    SELECT
        'Tablas fuera del modelo',
        '0',
        CAST((
            SELECT COUNT(*)
            FROM sys.tables
            WHERE name NOT IN (
                'Dim_Date', 'Dim_Product', 'Dim_Customer', 'Dim_Territory', 'Fact_Sales'
            )
        ) AS varchar(20))

    UNION ALL
    SELECT
        'Vistas',
        '0',
        CAST((SELECT COUNT(*) FROM sys.views) AS varchar(20))

    UNION ALL
    SELECT 'Filas Fact_Sales', '0', CAST((SELECT COUNT(*) FROM Fact_Sales) AS varchar(20))
    UNION ALL
    SELECT 'Filas Dim_Date', '0', CAST((SELECT COUNT(*) FROM Dim_Date) AS varchar(20))
    UNION ALL
    SELECT 'Filas Dim_Product', '0', CAST((SELECT COUNT(*) FROM Dim_Product) AS varchar(20))
    UNION ALL
    SELECT 'Filas Dim_Customer', '0', CAST((SELECT COUNT(*) FROM Dim_Customer) AS varchar(20))
    UNION ALL
    SELECT 'Filas Dim_Territory', '0', CAST((SELECT COUNT(*) FROM Dim_Territory) AS varchar(20))

    UNION ALL
    SELECT
        'Channel VARCHAR(10) NOT NULL',
        'varchar|10|0',
        (
            SELECT t.name + '|' + CAST(c.max_length AS varchar(10)) + '|' + CAST(c.is_nullable AS varchar(1))
            FROM sys.columns AS c
            INNER JOIN sys.types AS t ON t.user_type_id = c.user_type_id
            WHERE c.object_id = OBJECT_ID(N'dbo.Fact_Sales')
              AND c.name = 'Channel'
        )

    UNION ALL
    SELECT
        'UnitCost DECIMAL(19,4) NULL',
        'decimal|19|4|1',
        (
            SELECT t.name + '|' + CAST(c.precision AS varchar(10)) + '|' + CAST(c.scale AS varchar(10)) + '|' + CAST(c.is_nullable AS varchar(1))
            FROM sys.columns AS c
            INNER JOIN sys.types AS t ON t.user_type_id = c.user_type_id
            WHERE c.object_id = OBJECT_ID(N'dbo.Fact_Sales')
              AND c.name = 'UnitCost'
        )

    UNION ALL
    SELECT
        'LineCost DECIMAL(19,4) NULL',
        'decimal|19|4|1',
        (
            SELECT t.name + '|' + CAST(c.precision AS varchar(10)) + '|' + CAST(c.scale AS varchar(10)) + '|' + CAST(c.is_nullable AS varchar(1))
            FROM sys.columns AS c
            INNER JOIN sys.types AS t ON t.user_type_id = c.user_type_id
            WHERE c.object_id = OBJECT_ID(N'dbo.Fact_Sales')
              AND c.name = 'LineCost'
        )

    UNION ALL
    SELECT
        'Margin DECIMAL(19,4) NULL',
        'decimal|19|4|1',
        (
            SELECT t.name + '|' + CAST(c.precision AS varchar(10)) + '|' + CAST(c.scale AS varchar(10)) + '|' + CAST(c.is_nullable AS varchar(1))
            FROM sys.columns AS c
            INNER JOIN sys.types AS t ON t.user_type_id = c.user_type_id
            WHERE c.object_id = OBJECT_ID(N'dbo.Fact_Sales')
              AND c.name = 'Margin'
        )

    UNION ALL
    SELECT
        'SalesAmount DECIMAL(19,4) NOT NULL',
        'decimal|19|4|0',
        (
            SELECT t.name + '|' + CAST(c.precision AS varchar(10)) + '|' + CAST(c.scale AS varchar(10)) + '|' + CAST(c.is_nullable AS varchar(1))
            FROM sys.columns AS c
            INNER JOIN sys.types AS t ON t.user_type_id = c.user_type_id
            WHERE c.object_id = OBJECT_ID(N'dbo.Fact_Sales')
              AND c.name = 'SalesAmount'
        )

    UNION ALL
    SELECT
        'UnitPrice DECIMAL(19,4) NOT NULL',
        'decimal|19|4|0',
        (
            SELECT t.name + '|' + CAST(c.precision AS varchar(10)) + '|' + CAST(c.scale AS varchar(10)) + '|' + CAST(c.is_nullable AS varchar(1))
            FROM sys.columns AS c
            INNER JOIN sys.types AS t ON t.user_type_id = c.user_type_id
            WHERE c.object_id = OBJECT_ID(N'dbo.Fact_Sales')
              AND c.name = 'UnitPrice'
        )

    UNION ALL
    SELECT
        'Restriccion canal',
        '1',
        CAST((
            SELECT COUNT(*)
            FROM sys.check_constraints
            WHERE name = 'CK_FactSales_Channel'
              AND parent_object_id = OBJECT_ID(N'dbo.Fact_Sales')
        ) AS varchar(20))

    UNION ALL
    SELECT
        'Restriccion coste y margen juntos',
        '1',
        CAST((
            SELECT COUNT(*)
            FROM sys.check_constraints
            WHERE name = 'CK_FactSales_CosteMargen'
              AND parent_object_id = OBJECT_ID(N'dbo.Fact_Sales')
        ) AS varchar(20))

    UNION ALL
    SELECT
        'CustomerType Person o Store',
        '1',
        CAST((
            SELECT COUNT(*)
            FROM sys.check_constraints
            WHERE name = 'CK_DimCustomer_Type'
              AND parent_object_id = OBJECT_ID(N'dbo.Dim_Customer')
        ) AS varchar(20))

    UNION ALL
    SELECT
        'IDENTITY ProductKey CustomerKey TerritoryKey SalesKey',
        'CustomerKey,ProductKey,SalesKey,TerritoryKey',
        (
            SELECT STRING_AGG(c.name, ',') WITHIN GROUP (ORDER BY c.name)
            FROM sys.identity_columns AS c
            WHERE c.object_id IN (
                OBJECT_ID(N'dbo.Dim_Product'),
                OBJECT_ID(N'dbo.Dim_Customer'),
                OBJECT_ID(N'dbo.Dim_Territory'),
                OBJECT_ID(N'dbo.Fact_Sales')
            )
        )

    UNION ALL
    SELECT
        'DateKey sin IDENTITY',
        '0',
        CAST((
            SELECT COUNT(*)
            FROM sys.identity_columns
            WHERE object_id = OBJECT_ID(N'dbo.Dim_Date')
        ) AS varchar(20))

    UNION ALL
    SELECT
        'DateKey INT',
        'int|0',
        (
            SELECT t.name + '|' + CAST(c.is_nullable AS varchar(1))
            FROM sys.columns AS c
            INNER JOIN sys.types AS t ON t.user_type_id = c.user_type_id
            WHERE c.object_id = OBJECT_ID(N'dbo.Dim_Date')
              AND c.name = 'DateKey'
        )

    UNION ALL
    SELECT
        'Mes numerico',
        'int',
        (
            SELECT t.name
            FROM sys.columns AS c
            INNER JOIN sys.types AS t ON t.user_type_id = c.user_type_id
            WHERE c.object_id = OBJECT_ID(N'dbo.Dim_Date')
              AND c.name = 'Month'
        )

    UNION ALL
    SELECT
        'Claves de producto cliente territorio y fecha',
        '4',
        CAST((
            SELECT COUNT(*)
            FROM sys.foreign_keys
            WHERE parent_object_id = OBJECT_ID(N'dbo.Fact_Sales')
        ) AS varchar(20))

    UNION ALL
    SELECT
        'SalesOrderDetailID unico',
        '1',
        CAST((
            SELECT COUNT(*)
            FROM sys.indexes AS i
            INNER JOIN sys.index_columns AS ic
                ON ic.object_id = i.object_id AND ic.index_id = i.index_id
            INNER JOIN sys.columns AS c
                ON c.object_id = ic.object_id AND c.column_id = ic.column_id
            WHERE i.object_id = OBJECT_ID(N'dbo.Fact_Sales')
              AND i.is_unique = 1
              AND c.name = 'SalesOrderDetailID'
        ) AS varchar(20))

    UNION ALL
    SELECT
        'Sin columnas de flete ni impuesto',
        '0',
        CAST((
            SELECT COUNT(*)
            FROM sys.columns
            WHERE object_id = OBJECT_ID(N'dbo.Fact_Sales')
              AND name IN ('Freight', 'TaxAmt', 'Tax')
        ) AS varchar(20))

    UNION ALL
    SELECT
        'Lineas OLTP intactas',
        '121317',
        CAST((
            SELECT COUNT(*)
            FROM AdventureWorks2025.Sales.SalesOrderDetail
        ) AS varchar(20))
) AS pruebas
ORDER BY Resultado, Prueba;
GO
