/**
 * Type declarations for expo-router.
 *
 * expo-router ships its own types via the expo postinstall script.
 * This shim provides a minimal declaration when postinstall is skipped
 * (e.g. npm install --ignore-scripts in CI).
 */
declare module "expo-router" {
  import { ComponentType, ReactNode } from "react";
  import { ParamListBase, RouteProp } from "@react-navigation/native";

  export function useRouter(): {
    push: (href: string) => void;
    replace: (href: string) => void;
    back: () => void;
    prefetch: (href: string) => void;
  };

  export function useLocalSearchParams<
    T extends Record<string, string> = Record<string, string>,
  >(): T;

  export function useSegments(): string[];

  export type Href = string;

  interface StackScreenOptions {
    headerShown?: boolean;
    title?: string;
    presentation?: "card" | "modal" | "transparentModal";
    headerStyle?: Record<string, unknown>;
    headerTintColor?: string;
    headerTitleStyle?: Record<string, unknown>;
    headerShadowVisible?: boolean;
    headerLeft?: (props: { onPress?: () => void }) => ReactNode;
  }

  interface TabScreenOptions {
    title?: string;
    tabBarLabel?: string;
    tabBarIcon?: (props: { color: string; size: number; focused: boolean }) => ReactNode;
    headerShown?: boolean;
  }

  interface ScreenProps {
    name: string;
    options?: StackScreenOptions | TabScreenOptions;
    children?: ReactNode;
  }

  interface NavigatorProps {
    screenOptions?: Record<string, unknown>;
    children: ReactNode;
  }

  export const Stack: ComponentType<NavigatorProps> & {
    Screen: ComponentType<ScreenProps>;
  };

  export const Tabs: ComponentType<NavigatorProps> & {
    Screen: ComponentType<ScreenProps>;
  };
}
