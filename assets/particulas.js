(function () {
    if (window.__particulasAdventure) {
        return;
    }
    window.__particulasAdventure = true;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        return;
    }

    var canvas = document.createElement("canvas");
    canvas.id = "particulas";
    canvas.setAttribute("aria-hidden", "true");
    document.body.appendChild(canvas);
    var contexto = canvas.getContext("2d", { alpha: true });
    var partes = [];
    var cantidad = 26;
    var ancho = 0;
    var alto = 0;
    var activo = true;
    var ultimo = 0;

    function colores() {
        var oscuro = document.documentElement.getAttribute("data-tema") === "oscuro";
        if (oscuro) {
            return ["rgba(223,248,74,0.32)", "rgba(197,208,184,0.24)", "rgba(244,247,239,0.18)"];
        }
        return ["rgba(23,32,22,0.22)", "rgba(74,104,22,0.26)", "rgba(125,143,98,0.2)"];
    }

    function nacer(desdeAbajo) {
        return {
            x: ancho * (0.46 + Math.random() * 0.52),
            y: desdeAbajo ? alto + 6 : Math.random() * alto,
            r: 0.7 + Math.random() * 1.5,
            v: 7 + Math.random() * 12,
            drift: -8 + Math.random() * 5,
            tono: Math.floor(Math.random() * 3),
        };
    }

    function medir() {
        ancho = window.innerWidth;
        alto = window.innerHeight;
        canvas.width = ancho;
        canvas.height = alto;
    }

    function poblar() {
        partes = [];
        var i;
        for (i = 0; i < cantidad; i += 1) {
            partes.push(nacer(false));
        }
    }

    function cuadro(ahora) {
        if (!activo) {
            return;
        }
        var dt = ultimo ? Math.min(0.05, (ahora - ultimo) / 1000) : 0.016;
        ultimo = ahora;
        contexto.clearRect(0, 0, ancho, alto);
        var tinta = colores();
        var i;
        for (i = 0; i < partes.length; i += 1) {
            var parte = partes[i];
            parte.y -= parte.v * dt;
            parte.x += parte.drift * dt;
            if (parte.y < -8 || parte.x < -8 || parte.x > ancho + 8) {
                partes[i] = nacer(true);
                parte = partes[i];
            }
            contexto.beginPath();
            contexto.fillStyle = tinta[parte.tono];
            contexto.arc(parte.x, parte.y, parte.r, 0, Math.PI * 2);
            contexto.fill();
        }
        window.requestAnimationFrame(cuadro);
    }

    document.addEventListener("visibilitychange", function () {
        if (document.hidden) {
            activo = false;
            return;
        }
        if (!activo) {
            activo = true;
            ultimo = 0;
            window.requestAnimationFrame(cuadro);
        }
    });

    window.addEventListener("resize", function () {
        medir();
    });

    medir();
    poblar();
    window.requestAnimationFrame(cuadro);
})();
