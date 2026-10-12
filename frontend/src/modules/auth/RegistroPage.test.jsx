import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn() },
  setLogoutHandler: vi.fn(),
}));

import { api } from "@/lib/api";
import { AuthProvider } from "@/context/AuthContext";
import RegistroPage from "@/modules/auth/RegistroPage";

function renderRegistroPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <RegistroPage />
      </AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("RegistroPage", () => {
  it("muestra un mensaje de error cuando el correo ya está registrado", async () => {
    api.post.mockRejectedValueOnce({
      response: { data: { detail: "Ya existe una cuenta registrada con ese correo electrónico" } },
    });
    renderRegistroPage();

    fireEvent.change(screen.getByLabelText(/nombre de la empresa/i), { target: { value: "Mi Negocio" } });
    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: "ya-existe@negocio.com" },
    });
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: "clave-segura-123" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /acepto la política/i }));
    fireEvent.click(screen.getByRole("button", { name: /crear cuenta/i }));

    expect(await screen.findByText("Ya existe una cuenta registrada con ese correo electrónico")).toBeInTheDocument();
  });

  it("guarda el token y loguea automáticamente cuando el registro es exitoso", async () => {
    api.post.mockResolvedValueOnce({ data: { access_token: "token-nuevo", token_type: "bearer" } });
    api.get.mockResolvedValueOnce({
      data: {
        usuario: { id: "1", nombre_completo: "Administrador" },
        tenant: { id: "t1", nombre_empresa: "Mi Negocio" },
      },
    });
    renderRegistroPage();

    fireEvent.change(screen.getByLabelText(/nombre de la empresa/i), { target: { value: "Mi Negocio" } });
    fireEvent.change(screen.getByLabelText(/correo electrónico/i), { target: { value: "nuevo@negocio.com" } });
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: "clave-segura-123" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /acepto la política/i }));
    fireEvent.click(screen.getByRole("button", { name: /crear cuenta/i }));

    await waitFor(() => expect(localStorage.getItem("js_company_token")).toBe("token-nuevo"));
    expect(api.post).toHaveBeenCalledWith("/seguridad/registro", {
      nombre_empresa: "Mi Negocio",
      email: "nuevo@negocio.com",
      password: "clave-segura-123",
      acepta_condiciones: true,
    });
    // No debe pedir credenciales de nuevo: /seguridad/me se llama solo, sin un login aparte.
    expect(api.get).toHaveBeenCalledWith("/seguridad/me");
  });
  it("la casilla de aceptación nace DESMARCADA y sin marcarla no se envía nada", async () => {
    renderRegistroPage();
    const casilla = screen.getByRole("checkbox", { name: /acepto la política de tratamiento de datos y los términos y condiciones/i });
    expect(casilla).not.toBeChecked();

    fireEvent.change(screen.getByLabelText(/nombre de la empresa/i), { target: { value: "Mi Negocio" } });
    fireEvent.change(screen.getByLabelText(/correo electrónico/i), { target: { value: "nuevo@negocio.com" } });
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: "clave-segura-123" } });
    fireEvent.click(screen.getByRole("button", { name: /crear cuenta/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/debes aceptar la Política de tratamiento de datos/);
    expect(casilla).toHaveFocus();
    expect(casilla).toHaveAttribute("aria-invalid", "true");
    expect(api.post).not.toHaveBeenCalled();
  });

  it("los enlaces a los documentos abren en otra pestaña (no se pierde lo escrito)", () => {
    renderRegistroPage();
    for (const [nombre, ruta] of [[/^política de tratamiento de datos$/i, "/legal/privacidad"], [/^términos y condiciones$/i, "/legal/terminos"]]) {
      const enlaces = screen.getAllByRole("link", { name: nombre });
      const enCasilla = enlaces.find((a) => a.getAttribute("target") === "_blank");
      expect(enCasilla).toHaveAttribute("href", ruta);
      expect(enCasilla).toHaveAttribute("rel", expect.stringContaining("noopener"));
    }
  });
});