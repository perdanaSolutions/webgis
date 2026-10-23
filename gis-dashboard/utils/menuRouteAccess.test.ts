import { describe, expect, it } from "vitest";
import {
  findControllingMenus,
  resolveMenuRouteAccess,
  type MenuRouteNode,
} from "./menuRouteAccess";

const menus: MenuRouteNode[] = [
  {
    id: "ROLE-MENU",
    to: "/roles",
    children: [{ id: "role-child", to: "/roles/detail" }],
  },
  { id: "map-menu", to: "/map" },
  { id: "folder", to: "", children: [{ id: "user-menu", to: "users" }] },
  { id: "external", to: "https://example.com/roles" },
];

function access(path: string, allowedMenuIds: string[], catalogReady = true) {
  return resolveMenuRouteAccess({
    path,
    menus,
    allowedMenuIds,
    catalogReady,
  });
}

describe("resolveMenuRouteAccess", () => {
  it("selalu mengizinkan halaman shell dan superadmin", () => {
    expect(access("/dashboard", []).allowed).toBe(true);
    expect(access("/login", []).allowed).toBe(true);
    expect(
      resolveMenuRouteAccess({
        path: "/roles",
        menus,
        allowedMenuIds: [],
        isSuperAdmin: true,
        catalogReady: true,
      }).allowed,
    ).toBe(true);
  });

  it("menolak URL menu yang tidak ada di hak akses user", () => {
    expect(access("/roles", ["map-menu"])).toEqual({
      allowed: false,
      redirectTo: "/dashboard",
    });
    expect(access("/roles/", ["user-menu"]).allowed).toBe(false);
    expect(access("/USERS", ["user-menu"]).allowed).toBe(true);
    expect(access("/users", ["USER-MENU"]).allowed).toBe(true);
  });

  it("memakai menu yang paling spesifik", () => {
    expect(findControllingMenus(menus, "/roles/detail").map((item) => item.id)).toEqual([
      "role-child",
    ]);
    expect(access("/roles/detail", ["ROLE-MENU"]).allowed).toBe(false);
    expect(access("/roles/detail", ["role-child"]).allowed).toBe(true);
    expect(access("/roles/lain", ["ROLE-MENU"]).allowed).toBe(true);
  });

  it("menganggap path alias sebagai halaman aslinya", () => {
    expect(access("/transaski", ["map-menu"])).toEqual({
      allowed: false,
      redirectTo: "/dashboard",
    });
    expect(
      resolveMenuRouteAccess({
        path: "/transaski",
        menus: [{ id: "trx", to: "/transaski" }],
        allowedMenuIds: ["trx"],
        catalogReady: true,
      }).allowed,
    ).toBe(true);
    expect(
      resolveMenuRouteAccess({
        path: "/transaski",
        menus: [{ id: "trx", to: "/transaksi" }],
        allowedMenuIds: ["trx"],
        catalogReady: true,
      }).allowed,
    ).toBe(true);
  });

  it("menolak halaman aplikasi bila katalog belum siap atau tidak terdaftar", () => {
    expect(access("/permissions", ["map-menu"], false).allowed).toBe(false);
    expect(access("/permissions", ["map-menu"]).allowed).toBe(false);
    expect(access("/laporan-khusus", ["map-menu"]).allowed).toBe(true);
  });

  it("tidak menyamakan prefix yang hanya mirip", () => {
    expect(access("/roles", ["map-menu"]).allowed).toBe(false);
    expect(
      resolveMenuRouteAccess({
        path: "/roles",
        menus: [{ id: "mirip", to: "/role" }],
        allowedMenuIds: ["mirip"],
        catalogReady: true,
      }).allowed,
    ).toBe(false);
  });
});
