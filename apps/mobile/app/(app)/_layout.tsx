/**
 * UniServe — App Route Group Layout
 *
 * Tab navigator for the main (authenticated) application.
 * Placeholder tabs — real content in future phases.
 */
import { Tabs } from "expo-router";
import { Text } from "react-native";

export default function AppLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: true,
        tabBarActiveTintColor: "#2563eb",
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Home",
          tabBarLabel: "Home",
          tabBarIcon: ({ color }) => (
            <Text style={{ fontSize: 20, color }}>🏠</Text>
          ),
        }}
      />
    </Tabs>
  );
}
