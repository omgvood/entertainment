"use client";

import { useState } from "react";
import Image from "next/image";

function isUsableImage(url?: string): boolean {
  if (!url) return false;
  // svg-иконки (rating/difficulty/markers) — не годятся как карточка 400×300
  if (url.toLowerCase().endsWith(".svg")) return false;
  return true;
}

interface CardImageProps {
  imageUrl?: string;
  alt: string;
  placeholder: { gradient: string; emoji: string };
}

export function CardImage({ imageUrl, alt, placeholder }: CardImageProps) {
  const [errored, setErrored] = useState(false);

  if (!isUsableImage(imageUrl) || errored) {
    return (
      <div
        className={`absolute inset-0 bg-gradient-to-br ${placeholder.gradient} flex items-center justify-center text-6xl`}
        aria-hidden
      >
        {placeholder.emoji}
      </div>
    );
  }

  return (
    <Image
      src={imageUrl!}
      alt={alt}
      fill
      sizes="(min-width: 1200px) 25vw, (min-width: 768px) 33vw, 50vw"
      className="object-cover"
      unoptimized
      onError={() => setErrored(true)}
    />
  );
}
