import { api } from "@/lib/api";

/**
 * Descarga un PDF del backend (que exige el token JWT, por eso no basta con
 * un <a href>) y lo abre en una pestaña nueva. Devuelve una promesa para que
 * el botón pueda mostrar el spinner mientras se genera.
 */
export async function abrirPdf(url, nombreArchivo = "documento.pdf") {
  const { data } = await api.get(url, { responseType: "blob" });
  const blob = new Blob([data], { type: "application/pdf" });
  const enlace = URL.createObjectURL(blob);
  const ventana = window.open(enlace, "_blank", "noopener");
  if (!ventana) {
    // Bloqueador de ventanas emergentes: se descarga en su lugar.
    const a = document.createElement("a");
    a.href = enlace;
    a.download = nombreArchivo;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }
  setTimeout(() => URL.revokeObjectURL(enlace), 60_000);
}
