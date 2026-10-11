/**
 * UniServe — Cart stack route
 *
 * Kept for the floating CartBar "view cart" push. The rendering lives in
 * src/components/CartScreen.tsx, shared with the new Cart tab.
 */
import React from "react";
import CartScreen from "../../src/components/CartScreen";

export default function CartRoute() {
  return <CartScreen />;
}
