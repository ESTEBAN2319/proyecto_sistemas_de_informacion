/*
    Fase 1. Reescribe el esquema en estrella y deja el almacén vacío.

    Alcance:
        - Grano: una fila de Fact_Sales = una fila de Sales.SalesOrderDetail.
        - Importe de la línea: LineTotal, DECIMAL(19,4), columna SalesAmount.
        - Canal: Sales.SalesOrderHeader.OnlineOrderFlag. 1 = Internet, 0 = Resto.
          No se deduce de Dim_Customer.
        - Territorio: SalesOrderHeader.TerritoryID del pedido.
        - Coste: Production.ProductCostHistory.StandardCost vigente en OrderDate.
          UnitCost es ese coste unitario.
          LineCost = UnitCost * OrderQty.
          Margin = SalesAmount - LineCost.
          Si no hay coste, UnitCost, LineCost y Margin quedan NULL.
          La línea de venta no se elimina.
        - Flete e impuesto se quedan en la cabecera. No hay columna para ellos.
        - ProductKey, CustomerKey y TerritoryKey las asigna IDENTITY.
        - DateKey es AAAAMMDD. El año fiscal empieza el 1 de julio.
        - CustomerType: Store si el cliente tiene StoreID; si no, Person si tiene PersonID.

    No carga datos. No toca AdventureWorks2025.
    Ejecutar completo, de arriba abajo, en localhost\SQLEXPRESS.
*/

IF DB_ID(N'AdventureWorks_DWH') IS NULL
    CREATE DATABASE AdventureWorks_DWH;
GO

USE AdventureWorks_DWH;
GO

DROP VIEW IF EXISTS dbo.vw_FactInternetSales;
DROP VIEW IF EXISTS dbo.vw_Sales;
DROP TABLE IF EXISTS dbo.Fact_Sales;
DROP TABLE IF EXISTS dbo.stg_Fact;
DROP TABLE IF EXISTS dbo.stg_Product;
DROP TABLE IF EXISTS dbo.stg_Customer;
DROP TABLE IF EXISTS dbo.stg_Territory;
DROP TABLE IF EXISTS dbo.stg_Date;
DROP TABLE IF EXISTS dbo.Dim_Product;
DROP TABLE IF EXISTS dbo.Dim_Customer;
DROP TABLE IF EXISTS dbo.Dim_Territory;
DROP TABLE IF EXISTS dbo.Dim_Date;
GO

CREATE TABLE Dim_Date (
    DateKey INT PRIMARY KEY,                 -- AAAAMMDD. No es IDENTITY.
    FullDate DATE NOT NULL UNIQUE,
    CalendarYear INT NOT NULL,
    FiscalYear INT NOT NULL,                 -- empieza el 1 de julio: jul-dic pertenece al año siguiente
    Quarter INT NOT NULL,
    FiscalQuarter INT NOT NULL,
    Month INT NOT NULL,                      -- número de mes, para ordenar la serie
    MonthName VARCHAR(20) NOT NULL,
    Day INT NOT NULL,
    DayOfWeekName VARCHAR(20) NOT NULL
);

CREATE TABLE Dim_Product (
    ProductKey INT IDENTITY(1,1) PRIMARY KEY,
    ProductAlternateKey INT NOT NULL UNIQUE, -- Production.Product.ProductID
    ProductName NVARCHAR(50) NOT NULL,
    ProductNumber NVARCHAR(25) NOT NULL,
    Color NVARCHAR(15) NOT NULL,
    SubcategoryName NVARCHAR(50) NOT NULL,
    CategoryName NVARCHAR(50) NOT NULL
);

CREATE TABLE Dim_Customer (
    CustomerKey INT IDENTITY(1,1) PRIMARY KEY,
    CustomerAlternateKey INT NOT NULL UNIQUE, -- Sales.Customer.CustomerID
    CustomerType VARCHAR(10) NOT NULL,        -- Store si hay StoreID; si no, Person si hay PersonID
    CustomerName NVARCHAR(150) NOT NULL,
    CONSTRAINT CK_DimCustomer_Type CHECK (CustomerType IN ('Person', 'Store'))
);

CREATE TABLE Dim_Territory (
    TerritoryKey INT IDENTITY(1,1) PRIMARY KEY,
    TerritoryAlternateKey INT NOT NULL UNIQUE, -- Sales.SalesTerritory.TerritoryID del pedido
    TerritoryName NVARCHAR(50) NOT NULL,
    CountryRegionCode NVARCHAR(3) NOT NULL,
    TerritoryGroup NVARCHAR(50) NOT NULL
);

CREATE TABLE Fact_Sales (
    SalesKey INT IDENTITY(1,1) PRIMARY KEY,
    ProductKey INT NOT NULL,
    CustomerKey INT NOT NULL,
    TerritoryKey INT NOT NULL,               -- territorio del pedido, no del cliente
    OrderDateKey INT NOT NULL,
    SalesOrderNumber NVARCHAR(25) NOT NULL,
    SalesOrderDetailID INT NOT NULL UNIQUE,  -- grano: una línea de SalesOrderDetail
    Channel VARCHAR(10) NOT NULL,            -- Internet o Resto, desde OnlineOrderFlag
    OrderQty SMALLINT NOT NULL,
    UnitPrice DECIMAL(19,4) NOT NULL,
    DiscountPct DECIMAL(9,4) NOT NULL,
    SalesAmount DECIMAL(19,4) NOT NULL,      -- LineTotal
    UnitCost DECIMAL(19,4) NULL,             -- StandardCost vigente en OrderDate
    LineCost DECIMAL(19,4) NULL,             -- UnitCost * OrderQty
    Margin DECIMAL(19,4) NULL,               -- SalesAmount - LineCost

    CONSTRAINT CK_FactSales_Channel
        CHECK (Channel IN ('Internet', 'Resto')),
    CONSTRAINT CK_FactSales_CosteMargen
        CHECK (
            (UnitCost IS NULL AND LineCost IS NULL AND Margin IS NULL)
            OR (UnitCost IS NOT NULL AND LineCost IS NOT NULL AND Margin IS NOT NULL)
        ),
    CONSTRAINT FK_FactSales_Product
        FOREIGN KEY (ProductKey) REFERENCES Dim_Product (ProductKey),
    CONSTRAINT FK_FactSales_Customer
        FOREIGN KEY (CustomerKey) REFERENCES Dim_Customer (CustomerKey),
    CONSTRAINT FK_FactSales_Territory
        FOREIGN KEY (TerritoryKey) REFERENCES Dim_Territory (TerritoryKey),
    CONSTRAINT FK_FactSales_Date
        FOREIGN KEY (OrderDateKey) REFERENCES Dim_Date (DateKey)
);
GO

CREATE INDEX IX_FactSales_Product ON Fact_Sales (ProductKey);
CREATE INDEX IX_FactSales_Customer ON Fact_Sales (CustomerKey);
CREATE INDEX IX_FactSales_Territory ON Fact_Sales (TerritoryKey);
CREATE INDEX IX_FactSales_OrderDate ON Fact_Sales (OrderDateKey);
CREATE INDEX IX_FactSales_Channel ON Fact_Sales (Channel);
GO
