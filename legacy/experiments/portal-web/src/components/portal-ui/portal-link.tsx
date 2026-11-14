"use client";

import Link from "next/link";
import { createContext, useContext } from "react";
import type { ComponentProps } from "react";

export const PortalPathContext = createContext("");

export default function PortalLink({
  href,
  ...props
}: ComponentProps<typeof Link>) {
  const base = useContext(PortalPathContext);
  const destination =
    base &&
    typeof href === "string" &&
    /^\/(projects|employees|workflows|jobs|reports|notifications|operations|system)(?=\/|\?|$)/.test(
      href,
    )
      ? `${base}${href}`
      : href;
  return <Link href={destination} {...props} />;
}
