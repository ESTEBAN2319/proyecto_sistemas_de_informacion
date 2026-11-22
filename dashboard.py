"""
Dashboard de AdventureWorks. Cada informe es una página.

Hecho en esta entrega: Proceso y Control.
Control enseña el canal internet y, aparte, el total del almacén.
Sin filtros, internet tiene que ser 60.398 líneas y 29.358.677,22 USD.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pyodbc
from dash import Dash, Input, Output, callback, ctx, html

SERVER = r"localhost\SQLEXPRESS"
DWH_DB = "AdventureWorks_DWH"
CENTIMO = Decimal("0.0001")

ESPERADO = {
    "Internet": (60398, Decimal("29358677.2207")),
    "Resto": (60919, Decimal("80487704.2043")),
    "Almacen": (121317, Decimal("109846381.4250")),
}

CONSULTA = """
SELECT
    Channel,
    COUNT(*) AS Lineas,
    SUM(SalesAmount) AS Importe
FROM dbo.Fact_Sales
GROUP BY Channel
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


def cargar_control() -> dict[str, tuple[int, Decimal]]:
    controlador = elegir_controlador()
    conexion = pyodbc.connect(
        f"DRIVER={{{controlador}}};SERVER={SERVER};DATABASE={DWH_DB};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;",
        autocommit=True,
    )
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


CONTROL = None
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


asegurar_control()


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
                        html.H2("Control"),
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
                    html.H2("Canal internet"),
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
                    html.H2("El almacén, aparte"),
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


app = Dash(
    __name__,
    assets_folder=str(Path(__file__).resolve().parent / "assets"),
    title="AdventureWorks. Ventas de bicicletas por internet",
    update_title=None,
)

app.layout = html.Div(
    className="pagina",
    children=[
        html.Header(
            className="cabecera",
            children=[
                html.P("Bicicletas, accesorios, ropa", className="marca"),
                html.H1("AdventureWorks. Ventas por internet"),
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
            ],
        ),
        html.Div(
            id="vista-proceso",
            children=[
                html.Section(
                    className="bloque",
                    children=[
                        html.H2("Cómo se preparan los datos"),
                        html.P(
                            "El pedido nace en la base del día a día. Un proceso lo extrae, "
                            "lo transforma y lo carga en un almacén. A partir de ahí se puede sumar "
                            "sin volver a armar el pedido.",
                            className="nota",
                        ),
                        html.Img(
                            src="/assets/proceso.svg",
                            className="diagrama",
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
    ],
)


@callback(
    Output("vista-proceso", "style"),
    Output("vista-control", "style"),
    Output("nav-proceso", "className"),
    Output("nav-control", "className"),
    Input("nav-proceso", "n_clicks"),
    Input("nav-control", "n_clicks"),
)
def cambiar_pagina(proceso, control):
    if ctx.triggered_id == "nav-control":
        return {"display": "none"}, {"display": "block"}, "nav", "nav activo"
    return {"display": "block"}, {"display": "none"}, "nav activo", "nav"


if __name__ == "__main__":
    app.run(debug=False, dev_tools_ui=False)
