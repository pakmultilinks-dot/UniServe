/**
 * FoodImage — Food item image with category-based placeholder.
 *
 * When no image URL is available, shows a colored background
 * with the category icon. When image URL exists, loads the image.
 */

import React, { useState } from "react";
import { View, Image, StyleSheet, ViewStyle, ActivityIndicator } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import type { MenuCategory } from "@uniserve/shared-types";
import { bgColor } from "../theme";
import { resolveApiImageUrl } from "../config";

const CATEGORY_IMAGES: Record<string, string> = {
  breakfast: "https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=800&q=85",
  main_course: "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=800&q=85",
  side_dish: "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=800&q=85",
  dessert: "https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=800&q=85",
  beverage: "https://images.unsplash.com/photo-1517701604599-bb29b565090c?auto=format&fit=crop&w=800&q=85",
  snack: "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=800&q=85",
  salad: "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=800&q=85",
  soup: "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=800&q=85",
};

interface FoodImageProps {
  uri?: string | null;
  category?: MenuCategory | string;
  size?: number;
  borderRadius?: number;
  style?: ViewStyle;
}

export default function FoodImage({
  uri,
  category,
  size,
  borderRadius = 12,
  style,
}: FoodImageProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  // Persisted image references are host-independent ("/api/v1/static/…") —
  // resolve against the configured API origin before rendering; fall back
  // to the category placeholder on null, resolution failure, or load error.
  const imageUri = resolveApiImageUrl(uri) || CATEGORY_IMAGES[category ?? ""];
  const bgColorHex = "#f3ead8";

  const containerStyle: ViewStyle[] = [
    styles.container,
    { borderRadius },
    size ? { width: size, height: size } : undefined,
    style,
  ].filter(Boolean) as ViewStyle[];

  if (imageUri && !imageFailed) {
    return (
      <View style={containerStyle}>
        {/* Beige placeholder + spinner sit UNDER the image so slow loads
            never show a blank white box — the fixed container keeps the
            card geometry stable while pixels stream in. */}
        <View
          style={[
            StyleSheet.absoluteFill,
            { backgroundColor: bgColorHex, alignItems: "center", justifyContent: "center" },
          ]}
        >
          {isLoading && <ActivityIndicator size="small" color="#9ca3af" />}
        </View>
        <Image
          source={{ uri: imageUri }}
          style={[styles.image, { borderRadius }]}
          resizeMode="cover"
          onLoadEnd={() => setIsLoading(false)}
          onError={() => setImageFailed(true)}
        />
      </View>
    );
  }

  return (
    <View style={[containerStyle, { backgroundColor: bgColorHex }]}>
      <Ionicons name="restaurant-outline" size={28} color="#9ca3af" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  image: {
    width: "100%",
    height: "100%",
  },
});
