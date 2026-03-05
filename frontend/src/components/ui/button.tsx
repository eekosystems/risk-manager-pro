import { clsx } from "clsx";
import { type ButtonHTMLAttributes, forwardRef } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", className, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={clsx(
          "inline-flex items-center justify-center font-semibold transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-50",
          {
            "rounded-lg px-3 py-1.5 text-sm": size === "sm",
            "rounded-xl px-4 py-2.5 text-sm": size === "md",
            "rounded-xl px-6 py-3 text-base": size === "lg",
          },
          {
            "gradient-brand text-white shadow-lg shadow-brand-500/25 hover:shadow-xl hover:shadow-brand-500/30":
              variant === "primary",
            "border border-gray-200 bg-white text-gray-700 hover:border-brand-300 hover:bg-brand-50":
              variant === "secondary",
            "text-gray-600 hover:bg-gray-100 hover:text-gray-900":
              variant === "ghost",
            "bg-red-50 text-red-600 hover:bg-red-100": variant === "danger",
          },
          className,
        )}
        {...props}
      >
        {children}
      </button>
    );
  },
);

Button.displayName = "Button";
