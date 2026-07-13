const mensajesEl = document.getElementById("mensajes");
const traceEl = document.getElementById("trace");
const formEl = document.getElementById("form-chat");
const inputEl = document.getElementById("input-mensaje");

let historial = [];

function agregarMensaje(role, texto, datosClave = []) {
  const wrapper = document.createElement("div");
  wrapper.className = `mensaje mensaje--${role === "model" ? "bot" : "user"}`;

  const burbuja = document.createElement("div");
  burbuja.className = "mensaje__burbuja";
  burbuja.textContent = texto;

  if (datosClave.length > 0) {
    const datos = document.createElement("div");
    datos.className = "mensaje__datos";
    datosClave.forEach((d) => {
      const chip = document.createElement("span");
      chip.className = "mensaje__dato";
      chip.textContent = d;
      datos.appendChild(chip);
    });
    burbuja.appendChild(datos);
  }

  wrapper.appendChild(burbuja);
  mensajesEl.appendChild(wrapper);
  mensajesEl.scrollTop = mensajesEl.scrollHeight;
}

function actualizarTrace(trace) {
  if (!trace || trace.length === 0) {
    return;
  }
  traceEl.innerHTML = "";
  trace.forEach((paso) => {
    const entrada = document.createElement("div");
    entrada.className = "panel__entrada";

    const nombre = document.createElement("p");
    nombre.className = "panel__entrada-nombre";
    nombre.textContent = `${paso.tool}(${JSON.stringify(paso.argumentos)})`;

    const resultado = document.createElement("pre");
    resultado.textContent = JSON.stringify(paso.resultado, null, 2);

    entrada.appendChild(nombre);
    entrada.appendChild(resultado);
    traceEl.appendChild(entrada);
  });
}

formEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const mensaje = inputEl.value.trim();
  if (!mensaje) return;

  agregarMensaje("user", mensaje);
  inputEl.value = "";
  inputEl.disabled = true;

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ historial, mensaje }),
    });

    if (!resp.ok) {
      throw new Error(`Error del servidor: ${resp.status}`);
    }

    const data = await resp.json();
    agregarMensaje("model", data.respuesta, data.datos_clave);
    actualizarTrace(data.trace);

    historial.push({ role: "user", text: mensaje });
    historial.push({ role: "model", text: data.respuesta });
  } catch (err) {
    agregarMensaje("model", `Ocurrió un error: ${err.message}`);
  } finally {
    inputEl.disabled = false;
    inputEl.focus();
  }
});
