import type { Metadata } from "next";
import View from "./view";

export const metadata: Metadata = { title: "Token Counter" };

export default function Page() {
  return <View />;
}
