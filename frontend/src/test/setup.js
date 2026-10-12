import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// `findBy…`/`waitFor` esperan hasta 3 s (el valor por defecto es 1 s).
// 2026-10-02: con la máquina ocupada por otros programas, pruebas que guardan
// un formulario y esperan volver al listado ("Proveedores", "Compras")
// fallaban por llegar a los 1,1–1,5 s; solas pasan en ~1 s. Igual que el
// `testTimeout` de vite.config.js: un fallo real no se esconde, solo tarda
// más en reportarse.
configure({ asyncUtilTimeout: 3000 });
