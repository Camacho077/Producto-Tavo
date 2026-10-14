import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), defaults: { baseURL: "http://localhost:8002/api/v1" } },
  setLogoutHandler: vi.fn(),
}));

import { api } from "@/lib/api";
import { AuthProvider } from "@/context/AuthContext";
import LoginPage from "@/modules/auth/LoginPage";

function renderLoginPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe("LoginPage", () => {
  // Un error distinto según la causa (2026-10-13): sin backend, el compañero
  // veía "No se pudo iniciar sesión" y revisaba su contraseña.
  const intentarEntrar = () => {
    renderLoginPage();
    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: "admin@empresa.com" },
    });
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: "clave-mala" } });
    fireEvent.click(screen.getByRole("button", { name: /ingresar/i }));
  };

  it("credenciales malas (401): 'Correo o contraseña incorrectos.'", async () => {
    api.post.mockRejectedValueOnce({ response: { status: 401, data: { detail: "Correo o contraseña incorrectos." } } });
    intentarEntrar();
    expect(await screen.findByText("Correo o contraseña incorrectos.")).toBeInTheDocument();
  });

  it("sin conexión: dice a qué URL intentó llegar y que el backend no está corriendo", async () => {
    api.post.mockRejectedValueOnce({ code: "ERR_NETWORK", message: "Network Error" });
    intentarEntrar();
    expect(
      await screen.findByText("No se pudo conectar con el servidor en http://localhost:8002/api/v1. Verifica que el backend esté corriendo."),
    ).toBeInTheDocument();
  });

  it("otro error: el motivo que devuelve el backend, tal cual", async () => {
    api.post.mockRejectedValueOnce({ response: { status: 403, data: { detail: "Usuario inactivo" } } });
    intentarEntrar();
    expect(await screen.findByText("Usuario inactivo")).toBeInTheDocument();
  });

  it("envía recordarme=false por defecto y true al marcar la casilla", async () => {
    api.post.mockResolvedValue({ data: { access_token: "t", token_type: "bearer" } });
    api.get.mockResolvedValue({ data: { usuario: {}, tenant: {} } });
    const { unmount } = renderLoginPage();

    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: "admin@empresa.com" },
    });
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: "clave-segura-123" } });
    fireEvent.click(screen.getByRole("button", { name: /^ingresar$/i }));

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith("/seguridad/login", {
        email: "admin@empresa.com",
        password: "clave-segura-123",
        recordarme: false,
      })
    );

    unmount();
    localStorage.clear();
    vi.clearAllMocks();
    api.post.mockResolvedValue({ data: { access_token: "t", token_type: "bearer" } });
    api.get.mockResolvedValue({ data: { usuario: {}, tenant: {} } });
    renderLoginPage();

    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: "admin@empresa.com" },
    });
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: "clave-segura-123" } });
    fireEvent.click(screen.getByLabelText(/recordarme/i));
    fireEvent.click(screen.getByRole("button", { name: /^ingresar$/i }));

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith("/seguridad/login", {
        email: "admin@empresa.com",
        password: "clave-segura-123",
        recordarme: true,
      })
    );
  });

  it("'¿Olvidaste tu contraseña?' abre una explicación real, no un enlace muerto", async () => {
    renderLoginPage();

    fireEvent.click(screen.getByRole("button", { name: /olvidaste tu contraseña/i }));

    const dialogo = await screen.findByRole("dialog");
    expect(dialogo).toBeInTheDocument();
    expect(screen.getByText(/administrador de tu empresa/i)).toBeInTheDocument();
  });

  it("guarda el token y consulta /seguridad/me cuando el login es exitoso", async () => {
    api.post.mockResolvedValueOnce({ data: { access_token: "token-123", token_type: "bearer" } });
    api.get.mockResolvedValueOnce({
      data: { usuario: { id: "1", nombre_completo: "Admin" }, tenant: { id: "t1", nombre_empresa: "JS Company" } },
    });
    renderLoginPage();

    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: "admin@empresa.com" },
    });
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: "clave-segura-123" } });
    fireEvent.click(screen.getByRole("button", { name: /ingresar/i }));

    await waitFor(() => expect(localStorage.getItem("js_company_token")).toBe("token-123"));
    expect(api.get).toHaveBeenCalledWith("/seguridad/me");
  });
});
