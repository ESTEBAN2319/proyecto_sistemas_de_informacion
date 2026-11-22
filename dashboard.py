"""
Dashboard de AdventureWorks. Cada informe es una página.

Hecho en esta entrega: Proceso, Control, Tiempo y Producto y territorio.
Control enseña el canal internet y, aparte, el total del almacén.
Sin filtros, internet tiene que ser 60.398 líneas y 29.358.677,22 USD.
Tiempo abre con todo internet y luego admite filtros de año, territorio y categoría.
El año es el natural y el mes se ordena por su número.
Producto y territorio abre con todo internet: la categoría que explica el importe,
los productos de mayor importe dentro de esa categoría y el territorio del pedido.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import plotly.graph_objects as go
import pyodbc
from dash import Dash, Input, Output, callback, ctx, dcc, html

SERVER = r"localhost\SQLEXPRESS"
DWH_DB = "AdventureWorks_DWH"
CENTIMO = Decimal("0.0001")

ESPERADO = {
    "Internet": (60398, Decimal("29358677.2207")),
    "Resto": (60919, Decimal("80487704.2043")),
    "Almacen": (121317, Decimal("109846381.4250")),
}
TOP_PRODUCTOS = 8
BICI_AUSTRALIA_2024 = Decimal("3154931.6361")

CONSULTA = """
SELECT
    Channel,
    COUNT(*) AS Lineas,
    SUM(SalesAmount) AS Importe
FROM dbo.Fact_Sales
GROUP BY Channel
"""

CONSULTA_CORTE = """
SELECT
    d.CalendarYear,
    d.Month,
    MIN(d.MonthName) AS MonthName,
    t.TerritoryName,
    p.CategoryName,
    COUNT(*) AS Lineas,
    SUM(f.SalesAmount) AS Importe
FROM dbo.Fact_Sales AS f
INNER JOIN dbo.Dim_Date AS d
    ON d.DateKey = f.OrderDateKey
INNER JOIN dbo.Dim_Territory AS t
    ON t.TerritoryKey = f.TerritoryKey
INNER JOIN dbo.Dim_Product AS p
    ON p.ProductKey = f.ProductKey
WHERE f.Channel = 'Internet'
GROUP BY d.CalendarYear, d.Month, t.TerritoryName, p.CategoryName
"""

CONSULTA_PRODUCTO = """
SELECT
    d.CalendarYear,
    t.TerritoryName,
    p.CategoryName,
    p.SubcategoryName,
    p.ProductName,
    COUNT(*) AS Lineas,
    SUM(f.SalesAmount) AS Importe
FROM dbo.Fact_Sales AS f
INNER JOIN dbo.Dim_Date AS d
    ON d.DateKey = f.OrderDateKey
INNER JOIN dbo.Dim_Territory AS t
    ON t.TerritoryKey = f.TerritoryKey
INNER JOIN dbo.Dim_Product AS p
    ON p.ProductKey = f.ProductKey
WHERE f.Channel = 'Internet'
GROUP BY
    d.CalendarYear,
    t.TerritoryName,
    p.CategoryName,
    p.SubcategoryName,
    p.ProductName
"""

def elegir_controlador() -> str:
    instalados = list(pyodbc.drivers())
    for nombre in (
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server",
    ):
        if nombre in instalados:
            return nombre
    raise RuntimeError("No hay un controlador ODBC de SQL Server.")


def a_decimal(valor) -> Decimal:
    return Decimal(valor).quantize(CENTIMO)


def formato_importe(valor: Decimal, decimales: int) -> str:
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".") + " USD"


def formato_lineas(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def formato_diferencia(valor: Decimal) -> str:
    texto = formato_importe(abs(valor), 2)
    if valor > 0:
        return "+" + texto
    if valor < 0:
        return "-" + texto
    return texto


def formato_porcentaje(ratio: Decimal) -> str:
    puntos = (ratio * Decimal(100)).quantize(Decimal("0.01"))
    texto = f"{abs(puntos):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if puntos > 0:
        return f"+{texto} %"
    if puntos < 0:
        return f"-{texto} %"
    return f"{texto} %"


def conectar():
    controlador = elegir_controlador()
    return pyodbc.connect(
        f"DRIVER={{{controlador}}};SERVER={SERVER};DATABASE={DWH_DB};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;",
        autocommit=True,
    )


def cargar_control() -> dict[str, tuple[int, Decimal]]:
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute(CONSULTA)
        filas = {
            canal: (int(lineas), a_decimal(importe))
            for canal, lineas, importe in cursor.fetchall()
        }
    finally:
        conexion.close()

    if set(filas) != {"Internet", "Resto"}:
        raise RuntimeError(
            "Fact_Sales no trae los dos canales esperados: "
            + ", ".join(sorted(filas))
        )

    lineas_almacen = filas["Internet"][0] + filas["Resto"][0]
    importe_almacen = filas["Internet"][1] + filas["Resto"][1]
    filas["Almacen"] = (lineas_almacen, importe_almacen)

    for canal, (lineas, importe) in ESPERADO.items():
        leidas, suma = filas[canal]
        if leidas != lineas or suma != importe:
            raise RuntimeError(
                f"{canal} no cuadra con el control: {leidas} líneas y {suma} USD."
            )
    return filas


def cuadrar_internet(lineas: int, importe: Decimal, origen: str) -> None:
    esperadas, suma = ESPERADO["Internet"]
    if lineas != esperadas or importe != suma:
        raise RuntimeError(
            f"{origen} no cuadra con internet: {lineas} líneas y {importe} USD."
        )


def resumir(filas: list[dict]) -> tuple[list[dict], list[dict]]:
    anios: dict[int, dict] = {}
    meses: dict[int, dict] = {}
    for fila in filas:
        anio = anios.setdefault(
            fila["anio"],
            {
                "anio": fila["anio"],
                "importe": Decimal("0"),
                "lineas": 0,
                "meses_set": set(),
                "primer_mes": fila["mes"],
                "ultimo_mes": fila["mes"],
            },
        )
        anio["importe"] += fila["importe"]
        anio["lineas"] += fila["lineas"]
        anio["meses_set"].add(fila["mes"])
        anio["primer_mes"] = min(anio["primer_mes"], fila["mes"])
        anio["ultimo_mes"] = max(anio["ultimo_mes"], fila["mes"])
        mes = meses.setdefault(
            fila["mes"],
            {
                "mes": fila["mes"],
                "nombre": fila["nombre"],
                "importe": Decimal("0"),
                "lineas": 0,
            },
        )
        mes["importe"] += fila["importe"]
        mes["lineas"] += fila["lineas"]
    lista_anios = []
    for anio in sorted(anios.values(), key=lambda fila: fila["anio"]):
        anio["importe"] = a_decimal(anio["importe"])
        anio["meses"] = len(anio["meses_set"])
        lista_anios.append(anio)
    lista_meses = []
    for mes in sorted(meses.values(), key=lambda fila: fila["mes"]):
        mes["importe"] = a_decimal(mes["importe"])
        lista_meses.append(mes)
    return lista_anios, lista_meses


def opciones_de(cortes: list[dict]) -> dict[str, list[dict]]:
    importe_territorio: dict[str, Decimal] = {}
    importe_categoria: dict[str, Decimal] = {}
    anios = set()
    for fila in cortes:
        anios.add(fila["anio"])
        importe_territorio[fila["territorio"]] = (
            importe_territorio.get(fila["territorio"], Decimal("0")) + fila["importe"]
        )
        importe_categoria[fila["categoria"]] = (
            importe_categoria.get(fila["categoria"], Decimal("0")) + fila["importe"]
        )
    territorios = sorted(importe_territorio, key=lambda nombre: (-importe_territorio[nombre], nombre))
    categorias = sorted(importe_categoria, key=lambda nombre: (-importe_categoria[nombre], nombre))
    return {
        "anios": [{"label": str(anio), "value": anio} for anio in sorted(anios)],
        "territorios": [{"label": nombre, "value": nombre} for nombre in territorios],
        "categorias": [{"label": nombre, "value": nombre} for nombre in categorias],
    }


def cargar_tiempo() -> dict:
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute(CONSULTA_CORTE)
        cortes = [
            {
                "anio": int(anio),
                "mes": int(mes),
                "nombre": str(nombre).strip(),
                "territorio": str(territorio).strip(),
                "categoria": str(categoria).strip(),
                "lineas": int(lineas),
                "importe": a_decimal(importe),
            }
            for anio, mes, nombre, territorio, categoria, lineas, importe in cursor.fetchall()
        ]
    finally:
        conexion.close()

    if not cortes:
        raise RuntimeError("Internet no tiene filas para la página Tiempo.")
    cuadrar_internet(
        sum(fila["lineas"] for fila in cortes),
        sum((fila["importe"] for fila in cortes), Decimal("0")),
        "El corte de tiempo",
    )
    anios, meses = resumir(cortes)
    if len(anios) < 2:
        raise RuntimeError("Internet no tiene dos años naturales para comparar.")
    if [fila["mes"] for fila in meses] != list(range(1, 13)):
        raise RuntimeError("El mes de internet no cubre de enero a diciembre.")
    cuadrar_internet(
        sum(fila["lineas"] for fila in anios),
        sum((fila["importe"] for fila in anios), Decimal("0")),
        "El año natural",
    )
    cuadrar_internet(
        sum(fila["lineas"] for fila in meses),
        sum((fila["importe"] for fila in meses), Decimal("0")),
        "El mes",
    )
    anio_top = max(anios, key=lambda fila: (fila["importe"], fila["anio"]))
    if not any(fila["anio"] == anio_top["anio"] - 1 for fila in anios):
        raise RuntimeError(
            f"{anio_top['anio']} es el año de mayor importe y no tiene año anterior."
        )
    return {"cortes": cortes, "opciones": opciones_de(cortes)}


def cargar_producto() -> dict:
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute(CONSULTA_PRODUCTO)
        filas = [
            {
                "anio": int(anio),
                "territorio": str(territorio).strip(),
                "categoria": str(categoria).strip(),
                "subcategoria": str(subcategoria).strip(),
                "producto": str(producto).strip(),
                "lineas": int(lineas),
                "importe": a_decimal(importe),
            }
            for anio, territorio, categoria, subcategoria, producto, lineas, importe in cursor.fetchall()
        ]
    finally:
        conexion.close()

    if not filas:
        raise RuntimeError("Internet no tiene filas para la página Producto y territorio.")
    cuadrar_internet(
        sum(fila["lineas"] for fila in filas),
        sum((fila["importe"] for fila in filas), Decimal("0")),
        "El corte de producto y territorio",
    )
    combinacion = sum(
        (
            fila["importe"]
            for fila in filas
            if fila["anio"] == 2024
            and fila["territorio"] == "Australia"
            and fila["categoria"] == "Bikes"
        ),
        Decimal("0"),
    )
    if a_decimal(combinacion) != BICI_AUSTRALIA_2024:
        raise RuntimeError(
            "Bikes, Australia y 2024 no cuadran: "
            f"{a_decimal(combinacion)} USD."
        )
    return {"filas": filas, "opciones": opciones_de(filas)}


CONTROL = None
TIEMPO = None
PRODUCTO = None
ERROR_DATOS = None


def asegurar_control():
    global CONTROL, ERROR_DATOS
    if CONTROL is not None or ERROR_DATOS is not None:
        return CONTROL
    try:
        CONTROL = cargar_control()
    except pyodbc.Error as exc:
        ERROR_DATOS = str(exc)
    return CONTROL


def asegurar_tiempo():
    global TIEMPO, ERROR_DATOS
    if TIEMPO is not None or ERROR_DATOS is not None:
        return TIEMPO
    try:
        TIEMPO = cargar_tiempo()
    except pyodbc.Error as exc:
        ERROR_DATOS = str(exc)
    return TIEMPO


def asegurar_producto():
    global PRODUCTO, ERROR_DATOS
    if PRODUCTO is not None or ERROR_DATOS is not None:
        return PRODUCTO
    try:
        PRODUCTO = cargar_producto()
    except pyodbc.Error as exc:
        ERROR_DATOS = str(exc)
    return PRODUCTO


asegurar_control()
asegurar_tiempo()
asegurar_producto()


def pregunta(texto: str) -> html.P:
    return html.P(texto, className="pregunta")


def titulo(dibujo: str, texto: str) -> html.H2:
    return html.H2(
        [
            html.Span(className=f"icono icono-{dibujo}", **{"aria-hidden": "true"}),
            texto,
        ]
    )


def paleta(tema: str) -> dict[str, str]:
    if tema == "claro":
        return {
            "texto": "#3e4c38",
            "eje": "#172016",
            "rejilla": "#d3dcc8",
            "barra": "#7d8f62",
            "lider": "#c6de3a",
            "minimo": "#c4b48a",
            "hover_fondo": "#172016",
            "hover_texto": "#f4f7ef",
            "hover_borde": "#c6de3a",
        }
    return {
        "texto": "#c5d0b8",
        "eje": "#f4f7ef",
        "rejilla": "#2a3324",
        "barra": "#7d8f62",
        "lider": "#dff84a",
        "minimo": "#f4f7ef",
        "hover_fondo": "#171d14",
        "hover_texto": "#f4f7ef",
        "hover_borde": "#dff84a",
    }


def tema_valido(tema: str | None) -> str:
    return tema if tema in ("claro", "oscuro") else "claro"


def tarjeta(etiqueta: str, importe: str, lineas: str, clase: str) -> html.Div:
    return html.Div(
        className=clase,
        children=[
            html.Span(etiqueta),
            html.Strong(importe),
            html.Em(lineas),
        ],
    )


def vista_control() -> html.Div:
    if CONTROL is None:
        aviso = ERROR_DATOS or "No hay conexión con SQL Server Express."
        return html.Div(
            id="vista-control",
            style={"display": "none"},
            children=[
                html.Section(
                    className="bloque",
                    children=[
                        pregunta(
                            "¿Cuál es el importe del canal internet, "
                            "y cuántas líneas lo componen?"
                        ),
                        titulo("importe", "Control"),
                        html.P(aviso, className="nota"),
                    ],
                )
            ],
        )

    internet_lineas, internet_importe = CONTROL["Internet"]
    resto_lineas, resto_importe = CONTROL["Resto"]
    almacen_lineas, almacen_importe = CONTROL["Almacen"]
    return html.Div(
        id="vista-control",
        style={"display": "none"},
        children=[
            html.Section(
                className="bloque control-informe",
                children=[
                    pregunta(
                        "¿Cuál es el importe del canal internet, "
                        "y cuántas líneas lo componen?"
                    ),
                    titulo("importe", "Canal internet"),
                    html.P(
                        "Este es el número del informe. "
                        "Es el canal internet del almacén.",
                        className="nota",
                    ),
                    html.Div(
                        className="kpis kpis-dos",
                        children=[
                            tarjeta(
                                "Importe",
                                formato_importe(internet_importe, 2),
                                f"{formato_lineas(internet_lineas)} líneas",
                                "tarjeta tarjeta-informe",
                            ),
                            tarjeta(
                                "Líneas",
                                formato_lineas(internet_lineas),
                                "Una línea es una fila del pedido por internet",
                                "tarjeta tarjeta-informe",
                            ),
                        ],
                    ),
                ],
            ),
            html.Section(
                className="bloque control-almacen",
                children=[
                    titulo("almacen", "El almacén, aparte"),
                    html.P(
                        "El almacén guarda internet y el resto. "
                        f"{formato_importe(almacen_importe, 4)} es la suma de los dos canales. "
                        "No es la venta por internet.",
                        className="nota",
                    ),
                    html.Div(
                        className="kpis kpis-dos",
                        children=[
                            tarjeta(
                                "Almacén completo",
                                formato_importe(almacen_importe, 4),
                                f"{formato_lineas(almacen_lineas)} líneas",
                                "tarjeta tarjeta-aparte",
                            ),
                            tarjeta(
                                "Resto, el otro canal",
                                formato_importe(resto_importe, 4),
                                f"{formato_lineas(resto_lineas)} líneas. No entra en el informe.",
                                "tarjeta tarjeta-aparte",
                            ),
                        ],
                    ),
                    html.P(
                        "Internet más el resto cuadra con el almacén. "
                        "En la defensa, el importe de internet es "
                        f"{formato_importe(internet_importe, 2)}.",
                        className="conclusion",
                    ),
                ],
            ),
        ],
    )


def anio_completo(fila: dict) -> bool:
    return fila["primer_mes"] == 1 and fila["ultimo_mes"] == 12 and fila["meses"] == 12


def enumerar(partes: list[str]) -> str:
    if len(partes) == 1:
        return partes[0]
    return ", ".join(partes[:-1]) + " y " + partes[-1]


def figura_importe(
    etiquetas: list[str],
    importes: list[Decimal],
    colores: list[str],
    ticks: list[str] | None = None,
    tema: str = "claro",
) -> go.Figure:
    tono = paleta(tema_valido(tema))
    millones = [float(valor) / 1_000_000 for valor in importes]
    maximo = max(millones) if millones else 0
    if maximo > 6:
        paso = 2.0
    elif maximo > 2:
        paso = 1.0
    elif maximo > 0.5:
        paso = 0.5
    else:
        paso = 0.1
    tope = 0.0
    while tope < maximo * 1.08 or tope == 0:
        tope += paso
    marcas = []
    marca = 0.0
    while marca <= tope + paso / 100:
        marcas.append(round(marca, 2))
        marca += paso
    figura = go.Figure(
        data=[
            go.Bar(
                x=etiquetas,
                y=millones,
                marker_color=colores,
                customdata=[formato_importe(valor, 2) for valor in importes],
                hovertemplate="%{x}<br>%{customdata}<extra></extra>",
                hoverlabel=dict(
                    bgcolor=tono["hover_fondo"],
                    font_color=tono["hover_texto"],
                    bordercolor=tono["hover_borde"],
                ),
            )
        ]
    )
    figura.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=tono["texto"], family="Segoe UI, sans-serif", size=13),
        margin=dict(l=52, r=8, t=8, b=32),
        height=300,
        showlegend=False,
        bargap=0.32,
        xaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=etiquetas,
            tickmode="array",
            tickvals=etiquetas,
            ticktext=ticks or etiquetas,
            tickfont=dict(color=tono["eje"], size=12),
            automargin=True,
        ),
        yaxis=dict(
            title=dict(text="Millones USD", font=dict(size=12, color=tono["texto"])),
            gridcolor=tono["rejilla"],
            tickfont=dict(color=tono["eje"], size=12),
            zeroline=False,
            tickmode="array",
            tickvals=marcas,
            ticktext=[
                f"{marca:.1f}".replace(".", ",") if paso < 1 else str(int(marca))
                for marca in marcas
            ],
            range=[0, tope],
        ),
    )
    return figura


def parte(numerador: Decimal, denominador: Decimal) -> Decimal:
    if denominador == 0:
        return Decimal("0")
    return numerador / denominador


def formato_parte(ratio: Decimal) -> str:
    puntos = (ratio * Decimal(100)).quantize(Decimal("0.01"))
    texto = f"{puntos:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{texto} %"


def agrupar_importe(filas: list[dict], clave: str) -> list[dict]:
    grupos: dict[str, dict] = {}
    for fila in filas:
        nombre = fila[clave]
        grupo = grupos.get(nombre)
        if grupo is None:
            grupo = {"nombre": nombre, "importe": Decimal("0"), "lineas": 0}
            grupos[nombre] = grupo
        grupo["importe"] += fila["importe"]
        grupo["lineas"] += fila["lineas"]
    salida = []
    for grupo in grupos.values():
        grupo["importe"] = a_decimal(grupo["importe"])
        salida.append(grupo)
    salida.sort(key=lambda grupo: (-grupo["importe"], grupo["nombre"]))
    return salida


def marcas_eje(maximo: float) -> tuple[float, list[float], list[str]]:
    if maximo > 6:
        paso = 2.0
    elif maximo > 2:
        paso = 1.0
    elif maximo > 0.5:
        paso = 0.5
    elif maximo > 0.05:
        paso = 0.1
    else:
        paso = 0.01
    tope = 0.0
    while tope < maximo * 1.28 or tope == 0:
        tope += paso
    marcas = []
    marca = 0.0
    while marca <= tope + paso / 100:
        marcas.append(round(marca, 2))
        marca += paso
    if paso < 0.1:
        textos = [f"{valor:.2f}".replace(".", ",") for valor in marcas]
    elif paso < 1:
        textos = [f"{valor:.1f}".replace(".", ",") for valor in marcas]
    else:
        textos = [str(int(valor)) for valor in marcas]
    return tope, marcas, textos


def figura_horizontal(
    etiquetas: list[str],
    importes: list[Decimal],
    colores: list[str],
    alto: int,
    textos: list[str] | None = None,
    tema: str = "claro",
) -> go.Figure:
    tono = paleta(tema_valido(tema))
    millones = [float(valor) / 1_000_000 for valor in importes]
    maximo = max(millones) if millones else 0
    tope, marcas, marcas_texto = marcas_eje(maximo)
    barra = go.Bar(
        x=millones,
        y=etiquetas,
        orientation="h",
        marker_color=colores,
        customdata=[formato_importe(valor, 2) for valor in importes],
        hovertemplate="%{y}<br>%{customdata}<extra></extra>",
        hoverlabel=dict(
            bgcolor=tono["hover_fondo"],
            font_color=tono["hover_texto"],
            bordercolor=tono["hover_borde"],
        ),
        cliponaxis=False,
    )
    if textos is not None:
        barra.text = textos
        barra.textposition = "outside"
        barra.textfont = dict(color=tono["eje"], size=12)
    figura = go.Figure(data=[barra])
    figura.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=tono["texto"], family="Segoe UI, sans-serif", size=13),
        margin=dict(l=16, r=72, t=8, b=36),
        height=alto,
        showlegend=False,
        bargap=0.28,
        xaxis=dict(
            title=dict(text="Millones USD", font=dict(size=12, color=tono["texto"])),
            gridcolor=tono["rejilla"],
            tickfont=dict(color=tono["eje"], size=12),
            zeroline=False,
            tickmode="array",
            tickvals=marcas,
            ticktext=marcas_texto,
            range=[0, tope],
        ),
        yaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=list(reversed(etiquetas)),
            tickmode="array",
            tickvals=etiquetas,
            ticktext=etiquetas,
            tickfont=dict(color=tono["eje"], size=12),
            automargin=True,
        ),
    )
    return figura


def alto_barras(cantidad: int) -> int:
    return max(200, 48 + cantidad * 34)


def textos_parte(importes: list[Decimal]) -> list[str]:
    total = sum(importes, Decimal("0"))
    return [formato_parte(parte(valor, total)) for valor in importes]


def colores_lider(nombres: list[str], lider: str, tema: str = "claro") -> list[str]:
    tono = paleta(tema_valido(tema))
    return [tono["lider"] if nombre == lider else tono["barra"] for nombre in nombres]


def filas_del_corte(territorio: str | None, categoria: str | None, anio: int | None = None) -> list[dict]:
    salida = []
    for fila in TIEMPO["cortes"]:
        if territorio and fila["territorio"] != territorio:
            continue
        if categoria and fila["categoria"] != categoria:
            continue
        if anio is not None and fila["anio"] != anio:
            continue
        salida.append(fila)
    return salida


def texto_cobertura(anios: list[dict], nombres: dict[int, str]) -> str:
    parciales = []
    completos = []
    for fila in anios:
        if anio_completo(fila):
            completos.append(str(fila["anio"]))
            continue
        inicio = nombres[fila["primer_mes"]].lower()
        fin = nombres[fila["ultimo_mes"]].lower()
        if fila["meses"] == fila["ultimo_mes"] - fila["primer_mes"] + 1:
            parciales.append(f"{fila['anio']} va de {inicio} a {fin}")
        else:
            parciales.append(
                f"{fila['anio']} tiene {fila['meses']} meses, de {inicio} a {fin}"
            )
    cobertura = ""
    if parciales:
        cobertura += ". ".join(parciales) + ". "
    if completos:
        verbo = "están" if len(completos) > 1 else "está"
        cobertura += f"{enumerar(completos)} {verbo} completos. "
    return cobertura


def nota_tiempo(datos: dict) -> str:
    nombres = {fila["mes"]: fila["nombre"] for fila in datos["meses"]}
    return (
        "Canal internet y año natural. "
        + texto_cobertura(datos["anios"], nombres)
        + f"La variación es {datos['anio_top']['anio']} contra {datos['anio_anterior']['anio']}. "
        "El mes suma todos los años y se ordena de enero a diciembre. "
        "La barra amarilla marca el máximo. En los meses, la barra clara marca el mínimo."
    )


def descripcion_corte(anio: int | None, territorio: str | None, categoria: str | None) -> str:
    partes = []
    if anio is not None:
        partes.append(str(anio))
    if territorio:
        partes.append(territorio)
    if categoria:
        partes.append(categoria)
    return enumerar(partes)


def contenido_tiempo(anio, territorio, categoria, tema="claro"):
    tema = tema_valido(tema)
    tono = paleta(tema)
    anio = int(anio) if anio is not None and anio != "" else None
    territorio = territorio or None
    categoria = categoria or None
    contexto = filas_del_corte(territorio, categoria)
    if not contexto:
        return html.P(
            "Este corte no tiene ventas por internet. El total sigue en Control.",
            className="nota",
        )
    anios_ctx, meses_ctx = resumir(contexto)
    nombres = {fila["mes"]: fila["nombre"] for fila in meses_ctx}
    foco = filas_del_corte(territorio, categoria, anio)
    if not foco:
        return html.P(
            f"{anio} no tiene ventas por internet en este corte. El total sigue en Control.",
            className="nota",
        )
    _, meses = resumir(foco)
    for mes in meses:
        nombres.setdefault(mes["mes"], mes["nombre"])
    if anio is None:
        top = max(anios_ctx, key=lambda fila: (fila["importe"], fila["anio"]))
    else:
        top = next(fila for fila in anios_ctx if fila["anio"] == anio)
    previo = next((fila for fila in anios_ctx if fila["anio"] == top["anio"] - 1), None)
    mes_top = max(meses, key=lambda fila: (fila["importe"], -fila["mes"]))
    mes_bajo = min(meses, key=lambda fila: (fila["importe"], fila["mes"]))
    colores_anio = [
        tono["lider"] if fila["anio"] == top["anio"] else tono["barra"] for fila in anios_ctx
    ]
    colores_mes = []
    for fila in meses:
        if fila["mes"] == mes_top["mes"]:
            colores_mes.append(tono["lider"])
        elif fila["mes"] == mes_bajo["mes"]:
            colores_mes.append(tono["minimo"])
        else:
            colores_mes.append(tono["barra"])
    if anio is None and not territorio and not categoria and previo is not None:
        nota = nota_tiempo(
            {
                "anios": anios_ctx,
                "meses": meses,
                "anio_top": top,
                "anio_anterior": previo,
            }
        )
        frase_anio = (
            f"El año de mayor importe es {top['anio']}, con {formato_importe(top['importe'], 2)}."
        )
    else:
        corte = descripcion_corte(anio, territorio, categoria)
        if anio is None:
            meses_frase = "El mes suma los años de este corte y se ordena de enero a diciembre."
            frase_anio = (
                f"El año de mayor importe es {top['anio']}, con {formato_importe(top['importe'], 2)}."
            )
        else:
            meses_frase = f"Los meses son los de {anio} y se ordenan de enero a diciembre."
            frase_anio = f"El año del filtro es {top['anio']}, con {formato_importe(top['importe'], 2)}."
        nota = (
            f"Corte: {corte}. No sustituye al total de internet; ese sigue en Control. "
            + texto_cobertura(anios_ctx, nombres)
            + meses_frase
            + (
                " La barra amarilla marca el máximo."
                if anio is None
                else f" La barra amarilla del gráfico de años es {anio}."
            )
            + " En los meses, la barra clara marca el mínimo."
        )
    if previo is None or previo["importe"] == 0:
        variacion = tarjeta(
            f"Variación contra {top['anio'] - 1}",
            "Sin ventas",
            f"{top['anio'] - 1} no tiene importe en este corte",
            "tarjeta tarjeta-informe",
        )
        frase_var = f"{top['anio'] - 1} no tiene ventas en este corte, así que no hay variación."
    else:
        diferencia = top["importe"] - previo["importe"]
        ratio = diferencia / previo["importe"]
        variacion = tarjeta(
            f"Variación contra {previo['anio']}",
            formato_porcentaje(ratio),
            formato_diferencia(diferencia),
            "tarjeta tarjeta-informe",
        )
        frase_var = (
            f"Contra {previo['anio']} la variación es {formato_diferencia(diferencia)} "
            f"({formato_porcentaje(ratio)})."
        )
    titulo_mes = "Importe por mes" if anio is None else f"Importe por mes de {anio}"
    return html.Div(
        children=[
            html.P(nota, className="nota"),
            html.Div(
                className="kpis",
                children=[
                    tarjeta(
                        "Año de mayor importe" if anio is None else "Año del filtro",
                        str(top["anio"]),
                        formato_importe(top["importe"], 2),
                        "tarjeta tarjeta-informe",
                    ),
                    variacion,
                    tarjeta(
                        "Mes de mayor importe",
                        mes_top["nombre"],
                        formato_importe(mes_top["importe"], 2),
                        "tarjeta tarjeta-informe",
                    ),
                    tarjeta(
                        "Mes de menor importe",
                        mes_bajo["nombre"],
                        formato_importe(mes_bajo["importe"], 2),
                        "tarjeta tarjeta-informe",
                    ),
                ],
            ),
            html.Div(
                className="graficos",
                children=[
                    html.Div(
                        className="grafico",
                        children=[
                            html.H3("Importe por año natural"),
                            dcc.Graph(
                                figure=figura_importe(
                                    [str(fila["anio"]) for fila in anios_ctx],
                                    [fila["importe"] for fila in anios_ctx],
                                    colores_anio,
                                    tema=tema,
                                ),
                                config={"displayModeBar": False, "responsive": True},
                                style={"width": "100%", "height": "300px"},
                            ),
                        ],
                    ),
                    html.Div(
                        className="grafico",
                        children=[
                            html.H3(titulo_mes),
                            dcc.Graph(
                                figure=figura_importe(
                                    [fila["nombre"] for fila in meses],
                                    [fila["importe"] for fila in meses],
                                    colores_mes,
                                    ticks=[fila["nombre"][:3] for fila in meses],
                                    tema=tema,
                                ),
                                config={"displayModeBar": False, "responsive": True},
                                style={"width": "100%", "height": "300px"},
                            ),
                        ],
                    ),
                ],
            ),
            html.P(
                f"{frase_anio} {frase_var} "
                f"El mes de mayor importe es {mes_top['nombre'].lower()} "
                f"({formato_importe(mes_top['importe'], 2)}) "
                f"y el de menor es {mes_bajo['nombre'].lower()} "
                f"({formato_importe(mes_bajo['importe'], 2)}).",
                className="conclusion",
            ),
        ],
    )


def desplegable(etiqueta: str, identificador: str, opciones: list[dict]) -> html.Div:
    return html.Div(
        children=[
            html.Label(etiqueta, htmlFor=identificador),
            dcc.Dropdown(
                id=identificador,
                options=opciones,
                value=None,
                placeholder="Todos",
                clearable=True,
                labels={
                    "search": "Buscar",
                    "clear_search": "Borrar búsqueda",
                    "clear_selection": "Quitar",
                    "no_options_found": "Sin resultados",
                },
            ),
        ],
    )


def vista_tiempo() -> html.Div:
    if TIEMPO is None:
        aviso = ERROR_DATOS or "No hay conexión con SQL Server Express."
        opciones = {"anios": [], "territorios": [], "categorias": []}
        detalle = html.P(aviso, className="nota")
    else:
        opciones = TIEMPO["opciones"]
        detalle = contenido_tiempo(None, None, None)
    return html.Div(
        id="vista-tiempo",
        style={"display": "none"},
        children=[
            html.Section(
                className="bloque informe",
                children=[
                    pregunta(
                        "¿Cuál es el año de mayor importe, cómo varía contra el anterior, "
                        "y cuáles son el mes más alto y el más bajo?"
                    ),
                    titulo("calendario", "Tiempo"),
                    html.P(
                        "Al abrir, el corte es todo el canal internet. "
                        "Es la vista que responde el informe. "
                        "Después se puede cambiar el año natural, el territorio del pedido "
                        "o la categoría. Vacío significa todos.",
                        className="nota",
                    ),
                    html.Div(
                        className="filtros",
                        children=[
                            desplegable("Año natural", "filtro-anio", opciones["anios"]),
                            desplegable(
                                "Territorio del pedido",
                                "filtro-territorio",
                                opciones["territorios"],
                            ),
                            desplegable("Categoría", "filtro-categoria", opciones["categorias"]),
                        ],
                    ),
                    html.Button(
                        "Todo internet",
                        id="filtro-limpiar",
                        n_clicks=0,
                        className="limpiar",
                    ),
                    html.Div(id="tiempo-detalle", children=detalle),
                ],
            )
        ],
    )


def filas_producto(
    territorio: str | None,
    categoria: str | None,
    anio: int | None = None,
) -> list[dict]:
    salida = []
    for fila in PRODUCTO["filas"]:
        if territorio and fila["territorio"] != territorio:
            continue
        if categoria and fila["categoria"] != categoria:
            continue
        if anio is not None and fila["anio"] != anio:
            continue
        salida.append(fila)
    return salida


def grafico_barras(titulo: str, figura: go.Figure) -> html.Div:
    return html.Div(
        className="grafico",
        children=[
            html.H3(titulo),
            dcc.Graph(
                figure=figura,
                config={"displayModeBar": False, "responsive": True},
                style={"width": "100%", "height": f"{int(figura.layout.height)}px"},
            ),
        ],
    )


def alcance(anio: int | None, nombre: str | None) -> str:
    if anio is None and not nombre:
        return "del canal internet"
    if anio is None:
        return f"de {nombre}"
    if not nombre:
        return f"de {anio}"
    return f"de {nombre} en {anio}"


def lugar_corte(anio: int | None, territorio: str | None) -> str:
    if anio is None and not territorio:
        return "en internet"
    if anio is None:
        return f"en {territorio}"
    if not territorio:
        return f"en {anio}"
    return f"en {territorio} en {anio}"


def frase_subcategorias(nombre: str, subcategorias: list[dict], lugar: str) -> str:
    visibles = subcategorias[:3]
    partes = [
        f"{fila['nombre']} ({formato_importe(fila['importe'], 2)})" for fila in visibles
    ]
    sujeto = nombre if lugar == "en internet" else f"{nombre} {lugar}"
    if len(visibles) == 1:
        return f"Dentro de {sujeto}, el importe está en {partes[0]}."
    if len(subcategorias) <= 3:
        return f"Dentro de {sujeto}, el importe se reparte en {enumerar(partes)}."
    return f"Dentro de {sujeto}, el mayor importe está en {enumerar(partes)}."


def frase_productos(
    nombre: str,
    productos: list[dict],
    visibles: list[dict],
    total: Decimal,
    ambito: str,
) -> str:
    primero = visibles[0]
    if len(productos) == 1:
        return (
            f"El producto es {primero['nombre']} "
            f"({formato_importe(primero['importe'], 2)})."
        )
    importe_top = a_decimal(sum((fila["importe"] for fila in visibles), Decimal("0")))
    return (
        f"{nombre} tiene {formato_lineas(len(productos))} productos {ambito}. "
        f"Los {len(visibles)} de mayor importe suman {formato_importe(importe_top, 2)}, "
        f"el {formato_parte(parte(importe_top, total))} de {nombre}. "
        f"El primero es {primero['nombre']} ({formato_importe(primero['importe'], 2)})."
    )


def contenido_producto(anio, territorio, categoria, tema="claro"):
    tema = tema_valido(tema)
    anio = int(anio) if anio is not None and anio != "" else None
    territorio = territorio or None
    categoria = categoria or None
    contexto_categoria = filas_producto(territorio, None, anio)
    contexto_territorio = filas_producto(None, categoria, anio)
    foco = filas_producto(territorio, categoria, anio)
    if not contexto_categoria or not contexto_territorio or not foco:
        return html.P(
            "Este corte no tiene ventas por internet. El total sigue en Control.",
            className="nota",
        )

    categorias = agrupar_importe(contexto_categoria, "categoria")
    territorios = agrupar_importe(contexto_territorio, "territorio")
    if categoria:
        categoria_foco = next(fila for fila in categorias if fila["nombre"] == categoria)
    else:
        categoria_foco = categorias[0]
    if territorio:
        territorio_foco = next(fila for fila in territorios if fila["nombre"] == territorio)
    else:
        territorio_foco = territorios[0]

    productos_foco = [
        fila for fila in foco if fila["categoria"] == categoria_foco["nombre"]
    ]
    productos = agrupar_importe(productos_foco, "producto")
    subcategorias = agrupar_importe(productos_foco, "subcategoria")
    visibles = productos[:TOP_PRODUCTOS]
    importe_categorias = sum((fila["importe"] for fila in categorias), Decimal("0"))
    importe_territorios = sum((fila["importe"] for fila in territorios), Decimal("0"))
    importe_top = a_decimal(sum((fila["importe"] for fila in visibles), Decimal("0")))
    importe_foco = a_decimal(sum((fila["importe"] for fila in foco), Decimal("0")))
    hay_corte = anio is not None or bool(territorio) or bool(categoria)
    lugar = lugar_corte(anio, territorio)
    alcance_categoria = alcance(anio, territorio)
    alcance_territorio = alcance(anio, categoria)
    if not hay_corte:
        nota = (
            "Canal internet. La barra amarilla marca el máximo. "
            "Los productos son los de mayor importe de la categoría que explica el importe. "
            "El territorio es el del pedido."
        )
    else:
        nota = (
            f"Corte: {descripcion_corte(anio, territorio, categoria)}. "
            "No sustituye al total de internet; ese sigue en Control. "
            "La barra amarilla marca el máximo de este corte."
        )

    frase_reparto = frase_subcategorias(categoria_foco["nombre"], subcategorias, lugar)
    frase_lista = frase_productos(
        categoria_foco["nombre"],
        productos,
        visibles,
        categoria_foco["importe"],
        lugar,
    )
    if categoria and territorio:
        cuando = f" en {anio}" if anio is not None else ""
        cierre = (
            f"{categoria} en {territorio}{cuando} suma {formato_importe(importe_foco, 2)}. "
            f"Dentro de {territorio}{cuando}, {categoria} es el "
            f"{formato_parte(parte(categoria_foco['importe'], importe_categorias))} del importe. "
            f"Dentro de {categoria}{cuando}, {territorio} es el "
            f"{formato_parte(parte(territorio_foco['importe'], importe_territorios))} del importe. "
            f"{frase_reparto} {frase_lista}"
        )
    else:
        if categoria:
            frase_categoria = (
                f"La categoría del filtro es {categoria_foco['nombre']}, "
                f"con {formato_importe(categoria_foco['importe'], 2)}, "
                f"el {formato_parte(parte(categoria_foco['importe'], importe_categorias))} "
                f"{alcance_categoria}."
            )
        else:
            frase_categoria = (
                f"{categoria_foco['nombre']} explica el importe: "
                f"{formato_importe(categoria_foco['importe'], 2)}, "
                f"el {formato_parte(parte(categoria_foco['importe'], importe_categorias))} "
                f"{alcance_categoria}."
            )
        if territorio:
            frase_territorio = (
                f"El territorio del filtro es {territorio_foco['nombre']}, "
                f"con {formato_importe(territorio_foco['importe'], 2)}, "
                f"el {formato_parte(parte(territorio_foco['importe'], importe_territorios))} "
                f"{alcance_territorio}."
            )
        else:
            frase_territorio = (
                f"El territorio del pedido con mayor importe es {territorio_foco['nombre']} "
                f"({formato_importe(territorio_foco['importe'], 2)}, "
                f"el {formato_parte(parte(territorio_foco['importe'], importe_territorios))} "
                f"{alcance_territorio})."
            )
        cierre = f"{frase_categoria} {frase_reparto} {frase_lista} {frase_territorio}"

    if not hay_corte:
        lider_lineas = sorted(categorias, key=lambda fila: (-fila["lineas"], fila["nombre"]))[0]
        if lider_lineas["nombre"] != categoria_foco["nombre"]:
            cierre += (
                f" {lider_lineas['nombre']} suma {formato_lineas(lider_lineas['lineas'])} líneas "
                f"y {categoria_foco['nombre']} suma {formato_lineas(categoria_foco['lineas'])}. "
                "Esta página ordena por importe."
            )

    nombres_categoria = [fila["nombre"] for fila in categorias]
    importes_categoria = [fila["importe"] for fila in categorias]
    nombres_territorio = [fila["nombre"] for fila in territorios]
    importes_territorio = [fila["importe"] for fila in territorios]
    nombres_producto = [fila["nombre"] for fila in visibles]
    importes_producto = [fila["importe"] for fila in visibles]
    alto_lado = alto_barras(max(len(categorias), len(territorios)))
    return html.Div(
        children=[
            html.P(nota, className="nota"),
            html.Div(
                className="kpis",
                children=[
                    tarjeta(
                        "Categoría del filtro" if categoria else "Categoría que explica el importe",
                        categoria_foco["nombre"],
                        (
                            f"{formato_importe(categoria_foco['importe'], 2)} · "
                            f"{formato_parte(parte(categoria_foco['importe'], importe_categorias))} "
                            f"{alcance_categoria}"
                        ),
                        "tarjeta tarjeta-informe",
                    ),
                    tarjeta(
                        "Producto de mayor importe",
                        visibles[0]["nombre"],
                        (
                            f"{formato_importe(visibles[0]['importe'], 2)} · "
                            f"{formato_parte(parte(visibles[0]['importe'], categoria_foco['importe']))} "
                            f"de {categoria_foco['nombre']}"
                        ),
                        "tarjeta tarjeta-informe tarjeta-nombre",
                    ),
                    tarjeta(
                        f"Los {len(visibles)} de mayor importe",
                        formato_parte(parte(importe_top, categoria_foco["importe"])),
                        formato_importe(importe_top, 2),
                        "tarjeta tarjeta-informe",
                    ),
                    tarjeta(
                        "Territorio del filtro" if territorio else "Territorio del pedido",
                        territorio_foco["nombre"],
                        (
                            f"{formato_importe(territorio_foco['importe'], 2)} · "
                            f"{formato_parte(parte(territorio_foco['importe'], importe_territorios))} "
                            f"{alcance_territorio}"
                        ),
                        "tarjeta tarjeta-informe",
                    ),
                ],
            ),
            html.Div(
                className="graficos",
                children=[
                    grafico_barras(
                        "Importe por categoría",
                        figura_horizontal(
                            nombres_categoria,
                            importes_categoria,
                            colores_lider(nombres_categoria, categoria_foco["nombre"], tema),
                            alto_lado,
                            textos_parte(importes_categoria),
                            tema,
                        ),
                    ),
                    grafico_barras(
                        "Importe por territorio del pedido",
                        figura_horizontal(
                            nombres_territorio,
                            importes_territorio,
                            colores_lider(nombres_territorio, territorio_foco["nombre"], tema),
                            alto_lado,
                            textos_parte(importes_territorio),
                            tema,
                        ),
                    ),
                ],
            ),
            grafico_barras(
                f"Productos de mayor importe en {categoria_foco['nombre']}",
                figura_horizontal(
                    nombres_producto,
                    importes_producto,
                    colores_lider(nombres_producto, visibles[0]["nombre"], tema),
                    alto_barras(len(visibles)),
                    tema=tema,
                ),
            ),
            html.P(cierre, className="conclusion"),
        ],
    )


def vista_producto() -> html.Div:
    if PRODUCTO is None:
        aviso = ERROR_DATOS or "No hay conexión con SQL Server Express."
        opciones = {"anios": [], "territorios": [], "categorias": []}
        detalle = html.P(aviso, className="nota")
    else:
        opciones = PRODUCTO["opciones"]
        detalle = contenido_producto(None, None, None)
    return html.Div(
        id="vista-producto",
        style={"display": "none"},
        children=[
            html.Section(
                className="bloque informe",
                children=[
                    pregunta(
                        "¿Qué categoría explica el importe, qué productos la sostienen "
                        "y en qué territorio del pedido se vende?"
                    ),
                    titulo("territorio", "Producto y territorio"),
                    html.P(
                        "Al abrir, el corte es todo el canal internet. "
                        "Es la vista que responde el informe. "
                        "La categoría es la que explica el importe, "
                        "los productos son los de mayor importe dentro de esa categoría "
                        "y el territorio es el del pedido. "
                        "Después se puede cambiar el año natural, el territorio o la categoría. "
                        "Vacío significa todos.",
                        className="nota",
                    ),
                    html.Div(
                        className="filtros",
                        children=[
                            desplegable("Año natural", "producto-anio", opciones["anios"]),
                            desplegable(
                                "Territorio del pedido",
                                "producto-territorio",
                                opciones["territorios"],
                            ),
                            desplegable("Categoría", "producto-categoria", opciones["categorias"]),
                        ],
                    ),
                    html.Button(
                        "Todo internet",
                        id="producto-limpiar",
                        n_clicks=0,
                        className="limpiar",
                    ),
                    html.Div(id="producto-detalle", children=detalle),
                ],
            )
        ],
    )


app = Dash(
    __name__,
    assets_folder=str(Path(__file__).resolve().parent / "assets"),
    title="AdventureWorks. Ventas de bicicletas por internet",
    update_title=None,
)

app.index_string = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        <script>
            var temaInicial = "claro";
            try {
                var temaGuardado = localStorage.getItem("tema-adventure");
                if (temaGuardado === "claro" || temaGuardado === "oscuro") {
                    temaInicial = temaGuardado;
                }
            } catch (e) {}
            document.documentElement.setAttribute("data-tema", temaInicial);
        </script>
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""

app.layout = html.Div(
    className="pagina",
    children=[
        dcc.Store(id="tema", data="claro"),
        dcc.Interval(id="tema-inicio", interval=250, max_intervals=1, n_intervals=0),
        html.Header(
            className="cabecera",
            children=[
                html.Div(
                    className="cabecera-fila",
                    children=[
                        html.Div(
                            children=[
                                html.P("Bicicletas, accesorios, ropa", className="marca"),
                                html.H1("AdventureWorks. Ventas por internet"),
                            ]
                        ),
                        html.Div(
                            className="temas",
                            children=[
                                html.Button(
                                    "Claro",
                                    id="tema-claro",
                                    n_clicks=0,
                                    className="tema activo",
                                ),
                                html.Button("Oscuro", id="tema-oscuro", n_clicks=0, className="tema"),
                            ],
                        ),
                    ],
                ),
                html.P(
                    "El informe usa el canal internet. "
                    "En Control, sin filtros, tienen que verse "
                    f"{formato_lineas(ESPERADO['Internet'][0])} líneas y "
                    f"{formato_importe(ESPERADO['Internet'][1], 2)}. "
                    "El total del almacén se cita aparte."
                ),
            ],
        ),
        html.Nav(
            className="menu",
            children=[
                html.Button("Proceso", id="nav-proceso", n_clicks=0, className="nav activo"),
                html.Button("Control", id="nav-control", n_clicks=0, className="nav"),
                html.Button("Tiempo", id="nav-tiempo", n_clicks=0, className="nav"),
                html.Button(
                    "Producto y territorio",
                    id="nav-producto",
                    n_clicks=0,
                    className="nav",
                ),
            ],
        ),
        html.Div(
            id="vista-proceso",
            children=[
                html.Section(
                    className="bloque",
                    children=[
                        pregunta("¿Cómo llega un pedido hasta las cifras de internet?"),
                        titulo("flujo", "Cómo se preparan los datos"),
                        html.P(
                            "El pedido nace en la base del día a día. Un proceso lo extrae, "
                            "lo transforma y lo carga en un almacén. A partir de ahí se puede sumar "
                            "sin volver a armar el pedido.",
                            className="nota",
                        ),
                        html.Img(
                            src="/assets/proceso-claro.svg",
                            className="diagrama diagrama-claro",
                            alt=(
                                "Del pedido en AdventureWorks2025 al almacén en estrella. "
                                "El informe se queda con el canal internet."
                            ),
                        ),
                        html.Img(
                            src="/assets/proceso.svg",
                            className="diagrama diagrama-oscuro",
                            alt=(
                                "Del pedido en AdventureWorks2025 al almacén en estrella. "
                                "El informe se queda con el canal internet."
                            ),
                        ),
                        html.P(
                            "Internet: 60.398 líneas y 29.358.677,22 USD. "
                            "El almacén completo suma 121.317 líneas y 109.846.381,4250 USD. "
                            "Esa segunda cifra no es la de este informe.",
                            className="conclusion",
                        ),
                    ],
                ),
            ],
        ),
        vista_control(),
        vista_tiempo(),
        vista_producto(),
        html.Div(id="reajuste", style={"display": "none"}),
        html.Div(id="reajuste-filtros", style={"display": "none"}),
        html.Div(id="reajuste-producto", style={"display": "none"}),
        html.Div(id="reajuste-producto-filtros", style={"display": "none"}),
    ],
)


@callback(
    Output("vista-proceso", "style"),
    Output("vista-control", "style"),
    Output("vista-tiempo", "style"),
    Output("vista-producto", "style"),
    Output("nav-proceso", "className"),
    Output("nav-control", "className"),
    Output("nav-tiempo", "className"),
    Output("nav-producto", "className"),
    Input("nav-proceso", "n_clicks"),
    Input("nav-control", "n_clicks"),
    Input("nav-tiempo", "n_clicks"),
    Input("nav-producto", "n_clicks"),
)
def cambiar_pagina(proceso, control, tiempo, producto):
    oculto = {"display": "none"}
    visible = {"display": "block"}
    estilos = [oculto, oculto, oculto, oculto]
    clases = ["nav", "nav", "nav", "nav"]
    indice = {
        "nav-control": 1,
        "nav-tiempo": 2,
        "nav-producto": 3,
    }.get(ctx.triggered_id, 0)
    estilos[indice] = visible
    clases[indice] = "nav activo"
    return (*estilos, *clases)


@callback(
    Output("tiempo-detalle", "children"),
    Input("filtro-anio", "value"),
    Input("filtro-territorio", "value"),
    Input("filtro-categoria", "value"),
    Input("tema", "data"),
)
def actualizar_tiempo(anio, territorio, categoria, tema):
    if TIEMPO is None:
        aviso = ERROR_DATOS or "No hay conexión con SQL Server Express."
        return html.P(aviso, className="nota")
    return contenido_tiempo(anio, territorio, categoria, tema)


@callback(
    Output("filtro-anio", "value"),
    Output("filtro-territorio", "value"),
    Output("filtro-categoria", "value"),
    Input("filtro-limpiar", "n_clicks"),
    prevent_initial_call=True,
)
def limpiar_filtros(_clics):
    return None, None, None


@callback(
    Output("producto-detalle", "children"),
    Input("producto-anio", "value"),
    Input("producto-territorio", "value"),
    Input("producto-categoria", "value"),
    Input("tema", "data"),
)
def actualizar_producto(anio, territorio, categoria, tema):
    if PRODUCTO is None:
        aviso = ERROR_DATOS or "No hay conexión con SQL Server Express."
        return html.P(aviso, className="nota")
    return contenido_producto(anio, territorio, categoria, tema)


@callback(
    Output("producto-anio", "value"),
    Output("producto-territorio", "value"),
    Output("producto-categoria", "value"),
    Input("producto-limpiar", "n_clicks"),
    prevent_initial_call=True,
)
def limpiar_producto(_clics):
    return None, None, None


app.clientside_callback(
    """
    function(estilo) {
        if (!estilo || estilo.display === "none") {
            return window.dash_clientside.no_update;
        }
        window.requestAnimationFrame(function() {
            window.dispatchEvent(new Event("resize"));
        });
        return window.dash_clientside.no_update;
    }
    """,
    Output("reajuste", "children"),
    Input("vista-tiempo", "style"),
)


app.clientside_callback(
    """
    function() {
        window.requestAnimationFrame(function() {
            window.requestAnimationFrame(function() {
                window.dispatchEvent(new Event("resize"));
            });
        });
        return window.dash_clientside.no_update;
    }
    """,
    Output("reajuste-filtros", "children"),
    Input("tiempo-detalle", "children"),
)


app.clientside_callback(
    """
    function(estilo) {
        if (!estilo || estilo.display === "none") {
            return window.dash_clientside.no_update;
        }
        window.requestAnimationFrame(function() {
            window.dispatchEvent(new Event("resize"));
        });
        return window.dash_clientside.no_update;
    }
    """,
    Output("reajuste-producto", "children"),
    Input("vista-producto", "style"),
)


app.clientside_callback(
    """
    function() {
        window.requestAnimationFrame(function() {
            window.requestAnimationFrame(function() {
                window.dispatchEvent(new Event("resize"));
            });
        });
        return window.dash_clientside.no_update;
    }
    """,
    Output("reajuste-producto-filtros", "children"),
    Input("producto-detalle", "children"),
)


app.clientside_callback(
    """
    function(nOscuro, nClaro, tick) {
        var contexto = window.dash_clientside.callback_context || {};
        var id = contexto.triggered_id;
        if (!id && contexto.triggered && contexto.triggered.length) {
            id = String(contexto.triggered[0].prop_id || "").split(".")[0];
        }
        var elegido = "claro";
        if (id === "tema-claro" && nClaro) {
            elegido = "claro";
        } else if (id === "tema-oscuro" && nOscuro) {
            elegido = "oscuro";
        } else {
            try {
                var guardado = localStorage.getItem("tema-adventure");
                if (guardado === "claro" || guardado === "oscuro") {
                    elegido = guardado;
                }
            } catch (e) {}
        }
        if ((id === "tema-claro" && nClaro) || (id === "tema-oscuro" && nOscuro)) {
            try {
                localStorage.setItem("tema-adventure", elegido);
            } catch (e) {}
        }
        document.documentElement.setAttribute("data-tema", elegido);
        return elegido;
    }
    """,
    Output("tema", "data"),
    Input("tema-oscuro", "n_clicks"),
    Input("tema-claro", "n_clicks"),
    Input("tema-inicio", "n_intervals"),
)


app.clientside_callback(
    """
    function(tema) {
        var elegido = tema === "claro" ? "claro" : "oscuro";
        document.documentElement.setAttribute("data-tema", elegido);
        return [
            elegido === "oscuro" ? "tema activo" : "tema",
            elegido === "claro" ? "tema activo" : "tema"
        ];
    }
    """,
    Output("tema-oscuro", "className"),
    Output("tema-claro", "className"),
    Input("tema", "data"),
)


if __name__ == "__main__":
    app.run(debug=False, dev_tools_ui=False)
