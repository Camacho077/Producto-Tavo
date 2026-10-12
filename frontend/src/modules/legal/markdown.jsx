/**
 * Renderizador MÍNIMO del subconjunto de Markdown que usan los documentos
 * legales: títulos (#, ##), párrafos, listas (- y 1.), cita (>) para el aviso
 * de borrador, **negrita** y `código`. Produce elementos de React, nunca
 * HTML crudo (sin dangerouslySetInnerHTML). Sin librería: 0 KB extra.
 *
 * `{{campo}}` se reemplaza con `datos[campo]` (config/empresa.js); un
 * marcador sin valor queda visible tal cual, para que se note.
 */
export function rellenar(texto, datos) {
  return texto.replace(/\{\{(\w+)\}\}/g, (todo, campo) => (datos[campo] != null ? String(datos[campo]) : todo));
}

function enLinea(texto, clave) {
  return texto.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((trozo, i) => {
    if (trozo.startsWith("**") && trozo.endsWith("**")) return <strong key={`${clave}-${i}`}>{trozo.slice(2, -2)}</strong>;
    if (trozo.startsWith("`") && trozo.endsWith("`")) return <code key={`${clave}-${i}`}>{trozo.slice(1, -1)}</code>;
    return trozo;
  });
}

export function Markdown({ texto }) {
  const bloques = [];
  const lineas = texto.replace(/\r\n/g, "\n").split("\n");
  let i = 0;
  while (i < lineas.length) {
    const linea = lineas[i];
    if (!linea.trim()) {
      i++;
      continue;
    }
    const clave = `b${bloques.length}`;
    const titulo = /^(#{1,3})\s+(.*)$/.exec(linea);
    if (titulo) {
      const Nivel = `h${titulo[1].length}`;
      bloques.push(<Nivel key={clave}>{enLinea(titulo[2], clave)}</Nivel>);
      i++;
      continue;
    }
    const lista = /^(\s*)(-|\d+\.)\s+/.exec(linea);
    if (lista) {
      const ordenada = lista[2] !== "-";
      const items = [];
      while (i < lineas.length && /^\s*(-|\d+\.)\s+/.test(lineas[i])) {
        items.push(lineas[i].replace(/^\s*(-|\d+\.)\s+/, ""));
        i++;
      }
      const Lista = ordenada ? "ol" : "ul";
      bloques.push(
        <Lista key={clave}>
          {items.map((t, n) => (
            <li key={n}>{enLinea(t, `${clave}-${n}`)}</li>
          ))}
        </Lista>
      );
      continue;
    }
    if (linea.startsWith(">")) {
      const partes = [];
      while (i < lineas.length && lineas[i].startsWith(">")) {
        partes.push(lineas[i].replace(/^>\s?/, ""));
        i++;
      }
      bloques.push(
        <aside key={clave} className="legal__aviso" role="note">
          {enLinea(partes.join(" "), clave)}
        </aside>
      );
      continue;
    }
    const parrafo = [];
    while (i < lineas.length && lineas[i].trim() && !/^(#{1,3}\s|>|\s*(-|\d+\.)\s)/.test(lineas[i])) {
      parrafo.push(lineas[i]);
      i++;
    }
    bloques.push(<p key={clave}>{enLinea(parrafo.join(" "), clave)}</p>);
  }
  return bloques;
}
