"""
Fase 2. ETL de AdventureWorks2025 hacia AdventureWorks_DWH.

Orden:
    1. Fabricar Dim_Date (calendario y año fiscal julio-junio).
    2. Extraer producto, cliente y territorio ya aplanados.
    3. MERGE de dimensiones por clave de negocio. IDENTITY asigna la surrogada.
    4. Vaciar el hecho e insertarlo con canal, coste de la fecha y margen.

El tipo de cliente es Store si hay StoreID; si no, Person si hay PersonID.
El canal sale de OnlineOrderFlag: 1 = Internet, 0 = Resto.
El coste es el StandardCost vigente en OrderDate. Si no hay, UnitCost,
LineCost y Margin quedan vacíos y la línea se conserva.

Ejecutar dos veces seguidas: la segunda carga tiene que dejar los mismos
conteos de filas, importe, canal y coste.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pyodbc

SERVER = r"localhost\SQLEXPRESS"
SOURCE_DB = "AdventureWorks2025"
DWH_DB = "AdventureWorks_DWH"

MESES = (
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)
DIAS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
DESCONOCIDO = "Desconocido"

ESPERADO_LINEAS = 121317
ESPERADO_IMPORTE = Decimal("109846381.4250")
ESPERADO_INTERNET_LINEAS = 60398
ESPERADO_INTERNET_IMPORTE = Decimal("29358677.2207")
ESPERADO_INTERNET_SIN_COSTE = 0
ESPERADO_RESTO_LINEAS = 60919
ESPERADO_RESTO_SIN_COSTE = 64
ESPERADO_PERSONAS = 18484
ESPERADO_TIENDAS = 1336


def pick_driver() -> str:
    installed = list(pyodbc.drivers())
    for name in (
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server",
    ):
        if name in installed:
            return name
    raise RuntimeError(
        "No hay un controlador ODBC de SQL Server. Instalados: " + ", ".join(installed)
    )


def connect(database: str) -> pyodbc.Connection:
    driver = pick_driver()
    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={SERVER};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(connection_string, autocommit=False)


def fetch_frame(connection: pyodbc.Connection, sql: str) -> pd.DataFrame:
    cursor = connection.cursor()
    cursor.execute(sql)
    columns = [column[0] for column in cursor.description]
    frame = pd.DataFrame.from_records(cursor.fetchall(), columns=columns)
    cursor.close()
    return frame


def plain_rows(frame: pd.DataFrame) -> list[tuple]:
    rows: list[tuple] = []
    for record in frame.itertuples(index=False, name=None):
        values = []
        for value in record:
            if hasattr(value, "item") and not isinstance(value, str):
                value = value.item()
            values.append(value)
        rows.append(tuple(values))
    return rows


def insert_many(
    cursor: pyodbc.Cursor,
    sql: str,
    rows: list[tuple],
    sizes: list | None = None,
    size: int = 5000,
) -> None:
    cursor.fast_executemany = True
    if sizes is not None:
        cursor.setinputsizes(sizes)
    for start in range(0, len(rows), size):
        cursor.executemany(sql, rows[start : start + size])


def ensure_staging(cursor: pyodbc.Cursor) -> None:
    cursor.execute(
        """
        DROP TABLE IF EXISTS dbo.stg_Fact;
        DROP TABLE IF EXISTS dbo.stg_Product;
        DROP TABLE IF EXISTS dbo.stg_Customer;
        DROP TABLE IF EXISTS dbo.stg_Territory;
        DROP TABLE IF EXISTS dbo.stg_Date;

        CREATE TABLE dbo.stg_Date (
            DateKey INT NOT NULL,
            FullDate DATE NOT NULL,
            CalendarYear INT NOT NULL,
            FiscalYear INT NOT NULL,
            Quarter INT NOT NULL,
            FiscalQuarter INT NOT NULL,
            Month INT NOT NULL,
            MonthName VARCHAR(20) NOT NULL,
            Day INT NOT NULL,
            DayOfWeekName VARCHAR(20) NOT NULL
        );

        CREATE TABLE dbo.stg_Product (
            ProductAlternateKey INT NOT NULL,
            ProductName NVARCHAR(50) NOT NULL,
            ProductNumber NVARCHAR(25) NOT NULL,
            Color NVARCHAR(15) NOT NULL,
            SubcategoryName NVARCHAR(50) NOT NULL,
            CategoryName NVARCHAR(50) NOT NULL
        );

        CREATE TABLE dbo.stg_Customer (
            CustomerAlternateKey INT NOT NULL,
            CustomerType VARCHAR(10) NOT NULL,
            CustomerName NVARCHAR(150) NOT NULL
        );

        CREATE TABLE dbo.stg_Territory (
            TerritoryAlternateKey INT NOT NULL,
            TerritoryName NVARCHAR(50) NOT NULL,
            CountryRegionCode NVARCHAR(3) NOT NULL,
            TerritoryGroup NVARCHAR(50) NOT NULL
        );

        CREATE TABLE dbo.stg_Fact (
            ProductID INT NOT NULL,
            CustomerID INT NOT NULL,
            TerritoryID INT NOT NULL,
            OrderDateKey INT NOT NULL,
            SalesOrderNumber NVARCHAR(25) NOT NULL,
            SalesOrderDetailID INT NOT NULL,
            Channel VARCHAR(10) NOT NULL,
            OrderQty SMALLINT NOT NULL,
            UnitPrice DECIMAL(19,4) NOT NULL,
            DiscountPct DECIMAL(9,4) NOT NULL,
            SalesAmount DECIMAL(19,4) NOT NULL,
            UnitCost DECIMAL(19,4) NULL
        );
        """
    )


def fiscal_parts(day: date) -> tuple[int, int]:
    """Año fiscal de AdventureWorks: empieza el 1 de julio."""
    if day.month >= 7:
        fiscal_year = day.year + 1
        fiscal_quarter = 1 if day.month <= 9 else 2
    else:
        fiscal_year = day.year
        fiscal_quarter = 3 if day.month <= 3 else 4
    return fiscal_year, fiscal_quarter


def build_dim_date(first_day: date, last_order_day: date) -> list[tuple]:
    """Calendario continuo desde el primer pedido hasta un año después del último."""
    end = last_order_day + timedelta(days=365)
    rows: list[tuple] = []
    current = first_day
    while current <= end:
        fiscal_year, fiscal_quarter = fiscal_parts(current)
        rows.append(
            (
                current.year * 10000 + current.month * 100 + current.day,
                current,
                current.year,
                fiscal_year,
                (current.month - 1) // 3 + 1,
                fiscal_quarter,
                current.month,
                MESES[current.month],
                current.day,
                DIAS[current.weekday()],
            )
        )
        current += timedelta(days=1)
    return rows


def text_or_unknown(series: pd.Series, limit: int) -> pd.Series:
    cleaned = series.fillna(DESCONOCIDO).astype(str).str.strip()
    cleaned = cleaned.mask(cleaned.eq(""), DESCONOCIDO)
    return cleaned.str.slice(0, limit)


def load_dates(cursor: pyodbc.Cursor, source: pyodbc.Connection) -> int:
    bounds = fetch_frame(
        source,
        "SELECT MIN(OrderDate) AS MinDate, MAX(OrderDate) AS MaxDate FROM Sales.SalesOrderHeader",
    )
    first_day = pd.Timestamp(bounds.loc[0, "MinDate"]).date()
    last_day = pd.Timestamp(bounds.loc[0, "MaxDate"]).date()
    rows = build_dim_date(first_day, last_day)
    cursor.execute("TRUNCATE TABLE stg_Date")
    insert_many(
        cursor,
        """
        INSERT INTO stg_Date (
            DateKey, FullDate, CalendarYear, FiscalYear, Quarter, FiscalQuarter,
            Month, MonthName, Day, DayOfWeekName
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
        sizes=[
            pyodbc.SQL_INTEGER,
            pyodbc.SQL_TYPE_DATE,
            pyodbc.SQL_INTEGER,
            pyodbc.SQL_INTEGER,
            pyodbc.SQL_INTEGER,
            pyodbc.SQL_INTEGER,
            pyodbc.SQL_INTEGER,
            (pyodbc.SQL_VARCHAR, 20, 0),
            pyodbc.SQL_INTEGER,
            (pyodbc.SQL_VARCHAR, 20, 0),
        ],
    )
    cursor.execute(
        """
        MERGE Dim_Date AS target
        USING stg_Date AS source
            ON target.DateKey = source.DateKey
        WHEN MATCHED THEN
            UPDATE SET
                FullDate = source.FullDate,
                CalendarYear = source.CalendarYear,
                FiscalYear = source.FiscalYear,
                Quarter = source.Quarter,
                FiscalQuarter = source.FiscalQuarter,
                Month = source.Month,
                MonthName = source.MonthName,
                Day = source.Day,
                DayOfWeekName = source.DayOfWeekName
        WHEN NOT MATCHED THEN
            INSERT (
                DateKey, FullDate, CalendarYear, FiscalYear, Quarter, FiscalQuarter,
                Month, MonthName, Day, DayOfWeekName
            )
            VALUES (
                source.DateKey, source.FullDate, source.CalendarYear, source.FiscalYear,
                source.Quarter, source.FiscalQuarter, source.Month, source.MonthName,
                source.Day, source.DayOfWeekName
            );
        """
    )
    return len(rows)


def load_products(cursor: pyodbc.Cursor, source: pyodbc.Connection) -> int:
    frame = fetch_frame(
        source,
        """
        SELECT
            p.ProductID AS ProductAlternateKey,
            p.Name AS ProductName,
            p.ProductNumber,
            p.Color,
            sc.Name AS SubcategoryName,
            cat.Name AS CategoryName
        FROM Production.Product AS p
        LEFT JOIN Production.ProductSubcategory AS sc
            ON sc.ProductSubcategoryID = p.ProductSubcategoryID
        LEFT JOIN Production.ProductCategory AS cat
            ON cat.ProductCategoryID = sc.ProductCategoryID
        """,
    )
    frame["ProductAlternateKey"] = frame["ProductAlternateKey"].astype(int)
    frame["ProductName"] = text_or_unknown(frame["ProductName"], 50)
    frame["ProductNumber"] = text_or_unknown(frame["ProductNumber"], 25)
    frame["Color"] = text_or_unknown(frame["Color"], 15)
    frame["SubcategoryName"] = text_or_unknown(frame["SubcategoryName"], 50)
    frame["CategoryName"] = text_or_unknown(frame["CategoryName"], 50)
    rows = plain_rows(frame)
    cursor.execute("TRUNCATE TABLE stg_Product")
    insert_many(
        cursor,
        """
        INSERT INTO stg_Product (
            ProductAlternateKey, ProductName, ProductNumber, Color,
            SubcategoryName, CategoryName
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
        sizes=[
            pyodbc.SQL_INTEGER,
            (pyodbc.SQL_WVARCHAR, 50, 0),
            (pyodbc.SQL_WVARCHAR, 25, 0),
            (pyodbc.SQL_WVARCHAR, 15, 0),
            (pyodbc.SQL_WVARCHAR, 50, 0),
            (pyodbc.SQL_WVARCHAR, 50, 0),
        ],
    )
    cursor.execute(
        """
        MERGE Dim_Product AS target
        USING stg_Product AS source
            ON target.ProductAlternateKey = source.ProductAlternateKey
        WHEN MATCHED THEN
            UPDATE SET
                ProductName = source.ProductName,
                ProductNumber = source.ProductNumber,
                Color = source.Color,
                SubcategoryName = source.SubcategoryName,
                CategoryName = source.CategoryName
        WHEN NOT MATCHED THEN
            INSERT (
                ProductAlternateKey, ProductName, ProductNumber, Color,
                SubcategoryName, CategoryName
            )
            VALUES (
                source.ProductAlternateKey, source.ProductName, source.ProductNumber,
                source.Color, source.SubcategoryName, source.CategoryName
            );
        """
    )
    return len(rows)


def load_customers(cursor: pyodbc.Cursor, source: pyodbc.Connection) -> int:
    frame = fetch_frame(
        source,
        """
        SELECT
            c.CustomerID AS CustomerAlternateKey,
            CASE
                WHEN c.StoreID IS NOT NULL THEN 'Store'
                WHEN c.PersonID IS NOT NULL THEN 'Person'
            END AS CustomerType,
            CASE
                WHEN c.StoreID IS NOT NULL THEN s.Name
                ELSE CONCAT(p.FirstName, ' ', p.LastName)
            END AS CustomerName
        FROM Sales.Customer AS c
        LEFT JOIN Person.Person AS p
            ON p.BusinessEntityID = c.PersonID
        LEFT JOIN Sales.Store AS s
            ON s.BusinessEntityID = c.StoreID
        """,
    )
    frame["CustomerAlternateKey"] = frame["CustomerAlternateKey"].astype(int)
    frame["CustomerType"] = text_or_unknown(frame["CustomerType"], 10)
    frame["CustomerName"] = text_or_unknown(frame["CustomerName"], 150)
    rows = plain_rows(frame)
    cursor.execute("TRUNCATE TABLE stg_Customer")
    insert_many(
        cursor,
        """
        INSERT INTO stg_Customer (CustomerAlternateKey, CustomerType, CustomerName)
        VALUES (?, ?, ?)
        """,
        rows,
        sizes=[
            pyodbc.SQL_INTEGER,
            (pyodbc.SQL_VARCHAR, 10, 0),
            (pyodbc.SQL_WVARCHAR, 150, 0),
        ],
    )
    cursor.execute(
        """
        MERGE Dim_Customer AS target
        USING stg_Customer AS source
            ON target.CustomerAlternateKey = source.CustomerAlternateKey
        WHEN MATCHED THEN
            UPDATE SET
                CustomerType = source.CustomerType,
                CustomerName = source.CustomerName
        WHEN NOT MATCHED THEN
            INSERT (CustomerAlternateKey, CustomerType, CustomerName)
            VALUES (source.CustomerAlternateKey, source.CustomerType, source.CustomerName);
        """
    )
    return len(rows)


def load_territories(cursor: pyodbc.Cursor, source: pyodbc.Connection) -> int:
    frame = fetch_frame(
        source,
        """
        SELECT
            t.TerritoryID AS TerritoryAlternateKey,
            t.Name AS TerritoryName,
            t.CountryRegionCode,
            t.[Group] AS TerritoryGroup
        FROM Sales.SalesTerritory AS t
        """,
    )
    frame["TerritoryAlternateKey"] = frame["TerritoryAlternateKey"].astype(int)
    frame["TerritoryName"] = text_or_unknown(frame["TerritoryName"], 50)
    frame["CountryRegionCode"] = text_or_unknown(frame["CountryRegionCode"], 3)
    frame["TerritoryGroup"] = text_or_unknown(frame["TerritoryGroup"], 50)
    rows = plain_rows(frame)
    cursor.execute("TRUNCATE TABLE stg_Territory")
    insert_many(
        cursor,
        """
        INSERT INTO stg_Territory (
            TerritoryAlternateKey, TerritoryName, CountryRegionCode, TerritoryGroup
        ) VALUES (?, ?, ?, ?)
        """,
        rows,
        sizes=[
            pyodbc.SQL_INTEGER,
            (pyodbc.SQL_WVARCHAR, 50, 0),
            (pyodbc.SQL_WVARCHAR, 3, 0),
            (pyodbc.SQL_WVARCHAR, 50, 0),
        ],
    )
    cursor.execute(
        """
        MERGE Dim_Territory AS target
        USING stg_Territory AS source
            ON target.TerritoryAlternateKey = source.TerritoryAlternateKey
        WHEN MATCHED THEN
            UPDATE SET
                TerritoryName = source.TerritoryName,
                CountryRegionCode = source.CountryRegionCode,
                TerritoryGroup = source.TerritoryGroup
        WHEN NOT MATCHED THEN
            INSERT (
                TerritoryAlternateKey, TerritoryName, CountryRegionCode, TerritoryGroup
            )
            VALUES (
                source.TerritoryAlternateKey, source.TerritoryName,
                source.CountryRegionCode, source.TerritoryGroup
            );
        """
    )
    return len(rows)


def load_facts(cursor: pyodbc.Cursor, source: pyodbc.Connection) -> tuple[int, Decimal]:
    extract = source.cursor()
    extract.execute(
        """
        SELECT
            d.ProductID,
            h.CustomerID,
            h.TerritoryID,
            CONVERT(int, CONVERT(char(8), h.OrderDate, 112)) AS OrderDateKey,
            h.SalesOrderNumber,
            d.SalesOrderDetailID,
            CASE WHEN h.OnlineOrderFlag = 1 THEN 'Internet' ELSE 'Resto' END AS Channel,
            d.OrderQty,
            CAST(d.UnitPrice AS decimal(19,4)) AS UnitPrice,
            CAST(d.UnitPriceDiscount AS decimal(9,4)) AS DiscountPct,
            CAST(d.LineTotal AS decimal(19,4)) AS SalesAmount,
            CAST(c.StandardCost AS decimal(19,4)) AS UnitCost
        FROM Sales.SalesOrderDetail AS d
        INNER JOIN Sales.SalesOrderHeader AS h
            ON h.SalesOrderID = d.SalesOrderID
        LEFT JOIN Production.ProductCostHistory AS c
            ON c.ProductID = d.ProductID
           AND c.StartDate <= h.OrderDate
           AND (c.EndDate IS NULL OR h.OrderDate <= c.EndDate)
        """
    )
    rows: list[tuple] = []
    amount = Decimal("0")
    for (
        product_id,
        customer_id,
        territory_id,
        date_key,
        number,
        line_id,
        channel,
        qty,
        price,
        discount,
        sales,
        unit_cost,
    ) in extract:
        rows.append(
            (
                int(product_id),
                int(customer_id),
                int(territory_id),
                int(date_key),
                number,
                int(line_id),
                channel,
                int(qty),
                price,
                discount,
                sales,
                unit_cost,
            )
        )
        amount += sales
    extract.close()

    cursor.execute("TRUNCATE TABLE stg_Fact")
    insert_many(
        cursor,
        """
        INSERT INTO stg_Fact (
            ProductID, CustomerID, TerritoryID, OrderDateKey, SalesOrderNumber,
            SalesOrderDetailID, Channel, OrderQty, UnitPrice, DiscountPct,
            SalesAmount, UnitCost
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
        sizes=[
            pyodbc.SQL_INTEGER,
            pyodbc.SQL_INTEGER,
            pyodbc.SQL_INTEGER,
            pyodbc.SQL_INTEGER,
            (pyodbc.SQL_WVARCHAR, 25, 0),
            pyodbc.SQL_INTEGER,
            (pyodbc.SQL_VARCHAR, 10, 0),
            pyodbc.SQL_SMALLINT,
            (pyodbc.SQL_DECIMAL, 19, 4),
            (pyodbc.SQL_DECIMAL, 9, 4),
            (pyodbc.SQL_DECIMAL, 19, 4),
            (pyodbc.SQL_DECIMAL, 19, 4),
        ],
    )
    cursor.execute("TRUNCATE TABLE Fact_Sales")
    cursor.execute(
        """
        INSERT INTO Fact_Sales (
            ProductKey, CustomerKey, TerritoryKey, OrderDateKey, SalesOrderNumber,
            SalesOrderDetailID, Channel, OrderQty, UnitPrice, DiscountPct,
            SalesAmount, UnitCost, LineCost, Margin
        )
        SELECT
            p.ProductKey,
            c.CustomerKey,
            t.TerritoryKey,
            f.OrderDateKey,
            f.SalesOrderNumber,
            f.SalesOrderDetailID,
            f.Channel,
            f.OrderQty,
            f.UnitPrice,
            f.DiscountPct,
            f.SalesAmount,
            f.UnitCost,
            CAST(f.UnitCost * f.OrderQty AS decimal(19,4)),
            CAST(f.SalesAmount - (f.UnitCost * f.OrderQty) AS decimal(19,4))
        FROM stg_Fact AS f
        INNER JOIN Dim_Product AS p
            ON p.ProductAlternateKey = f.ProductID
        INNER JOIN Dim_Customer AS c
            ON c.CustomerAlternateKey = f.CustomerID
        INNER JOIN Dim_Territory AS t
            ON t.TerritoryAlternateKey = f.TerritoryID
        INNER JOIN Dim_Date AS d
            ON d.DateKey = f.OrderDateKey
        """
    )
    return len(rows), amount


def reconcile(cursor: pyodbc.Cursor, source: pyodbc.Connection, staged_rows: int, staged_amount: Decimal) -> None:
    source_cursor = source.cursor()
    source_cursor.execute(
        """
        SELECT
            COUNT(*) AS Lineas,
            SUM(CAST(LineTotal AS decimal(19,4))) AS Importe
        FROM Sales.SalesOrderDetail
        """
    )
    source_rows, source_amount = source_cursor.fetchone()
    source_cursor.close()

    cursor.execute("SELECT COUNT(*) AS Lineas, SUM(SalesAmount) AS Importe FROM Fact_Sales")
    fact_rows, fact_amount = cursor.fetchone()
    cursor.execute(
        """
        SELECT
            Channel,
            COUNT(*) AS Lineas,
            SUM(SalesAmount) AS Importe,
            SUM(CASE WHEN UnitCost IS NULL THEN 1 ELSE 0 END) AS SinCoste,
            SUM(CASE WHEN Margin IS NULL THEN 1 ELSE 0 END) AS SinMargen
        FROM Fact_Sales
        GROUP BY Channel
        """
    )
    by_channel = {row.Channel: row for row in cursor.fetchall()}
    cursor.execute(
        """
        SELECT
            SUM(CASE WHEN CustomerType = 'Person' THEN 1 ELSE 0 END) AS Personas,
            SUM(CASE WHEN CustomerType = 'Store' THEN 1 ELSE 0 END) AS Tiendas
        FROM Dim_Customer
        """
    )
    persons, stores = cursor.fetchone()

    internet = by_channel.get("Internet")
    resto = by_channel.get("Resto")
    internet_rows = int(internet.Lineas) if internet else 0
    internet_amount = internet.Importe if internet else Decimal("0")
    internet_without_cost = int(internet.SinCoste) if internet else 0
    resto_rows = int(resto.Lineas) if resto else 0
    resto_without_cost = int(resto.SinCoste) if resto else 0
    resto_without_margin = int(resto.SinMargen) if resto else 0

    print(f"Lineas origen:  {int(source_rows)}")
    print(f"Lineas staging: {staged_rows}")
    print(f"Lineas hecho:   {int(fact_rows)}")
    print(f"Importe origen:  {source_amount}")
    print(f"Importe staging: {staged_amount}")
    print(f"Importe hecho:   {fact_amount}")
    print(f"Internet: {internet_rows} lineas, {internet_amount}, sin coste {internet_without_cost}")
    print(f"Resto:    {resto_rows} lineas, sin coste {resto_without_cost}, sin margen {resto_without_margin}")
    print(f"Personas: {int(persons)} | Tiendas: {int(stores)}")

    errors: list[str] = []
    if int(fact_rows) != ESPERADO_LINEAS or int(source_rows) != ESPERADO_LINEAS or staged_rows != ESPERADO_LINEAS:
        errors.append("El hecho no conserva 121317 lineas de SalesOrderDetail.")
    if fact_amount != ESPERADO_IMPORTE or source_amount != ESPERADO_IMPORTE or staged_amount != ESPERADO_IMPORTE:
        errors.append("La suma de SalesAmount no es 109846381.4250.")
    if internet_rows != ESPERADO_INTERNET_LINEAS or internet_amount != ESPERADO_INTERNET_IMPORTE:
        errors.append("El canal Internet no cuadra 60398 lineas y 29358677.2207.")
    if internet_without_cost != ESPERADO_INTERNET_SIN_COSTE:
        errors.append("Internet tiene filas sin coste.")
    if resto_rows != ESPERADO_RESTO_LINEAS or resto_without_cost != ESPERADO_RESTO_SIN_COSTE:
        errors.append("El canal Resto no cuadra 60919 lineas y 64 sin coste.")
    if resto_without_margin != ESPERADO_RESTO_SIN_COSTE:
        errors.append("Las 64 filas sin coste del resto no dejaron el margen vacio.")
    if int(persons) != ESPERADO_PERSONAS or int(stores) != ESPERADO_TIENDAS:
        errors.append("Dim_Customer no conserva 18484 personas y 1336 tiendas.")
    if errors:
        raise RuntimeError(" ".join(errors))


def main() -> None:
    source = connect(SOURCE_DB)
    warehouse = connect(DWH_DB)
    cursor = warehouse.cursor()
    try:
        ensure_staging(cursor)
        dates = load_dates(cursor, source)
        products = load_products(cursor, source)
        customers = load_customers(cursor, source)
        territories = load_territories(cursor, source)
        print(f"Dim_Date: {dates}")
        print(f"Dim_Product: {products}")
        print(f"Dim_Customer: {customers}")
        print(f"Dim_Territory: {territories}")
        staged_rows, staged_amount = load_facts(cursor, source)
        reconcile(cursor, source, staged_rows, staged_amount)
        warehouse.commit()
        print("Carga confirmada.")
    except Exception:
        warehouse.rollback()
        raise
    finally:
        cursor.close()
        source.close()
        warehouse.close()


if __name__ == "__main__":
    main()
