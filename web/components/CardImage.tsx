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
  /** Цена поверх плейсхолдера, когда картинки нет — тикет 13, вариант D. */
  priceLabel?: string;
}

export function CardImage({ imageUrl, alt, placeholder, priceLabel }: CardImageProps) {
  const [errored, setErrored] = useState(false);

  if (!isUsableImage(imageUrl) || errored) {
    return (
      <div
        className={`absolute inset-0 bg-gradient-to-br ${placeholder.gradient} flex items-center justify-center text-6xl`}
        aria-hidden
      >
        {placeholder.emoji}
        {priceLabel && (
          <span className="absolute bottom-2 left-1/2 -translate-x-1/2 text-[11.5px] font-semibold text-white/90 bg-black/35 px-3 py-1 rounded-full line-clamp-1 max-w-[90%]">
            {priceLabel}
          </span>
        )}
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
