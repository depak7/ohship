import { cn } from "@/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium tracking-wide",
  {
    variants: {
      variant: {
        default: "bg-[#ece6da] text-[var(--ink)]",
        draft: "bg-[#ece6da] text-[var(--muted)]",
        in_review: "bg-[#fff1d6] text-[var(--warn)]",
        changes_requested: "bg-[#fde8e6] text-[var(--danger)]",
        approved: "bg-[var(--accent-soft)] text-[var(--accent)]",
        in_progress: "bg-[#e4eefc] text-[var(--done)]",
        done: "bg-[#e4eefc] text-[var(--done)]",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export function Button({
  className,
  variant = "default",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "outline" | "ghost" | "destructive";
  // React 19 passes `ref` through as a regular prop — it just isn't in ButtonHTMLAttributes.
  ref?: React.Ref<HTMLButtonElement>;
}) {
  const variants = {
    default: "bg-[var(--ink)] text-[var(--bg)] hover:bg-[#243029]",
    outline: "border border-[var(--line)] bg-transparent hover:bg-white/60 text-[var(--ink)]",
    ghost: "bg-transparent hover:bg-black/5 text-[var(--ink)]",
    destructive: "bg-[var(--danger)] text-white hover:opacity-90",
  };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition disabled:opacity-50",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}

export function Card({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("surface rounded-2xl p-6", className)}
      {...props}
    />
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className="w-full rounded-xl border border-[var(--line)] bg-white/70 px-3 py-2.5 text-sm outline-none ring-[var(--accent)] focus:ring-2"
      {...props}
    />
  );
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className="w-full rounded-xl border border-[var(--line)] bg-white/70 px-3 py-2.5 text-sm outline-none ring-[var(--accent)] focus:ring-2"
      {...props}
    />
  );
}

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className={cn("mb-1.5 block text-sm font-medium text-[var(--muted)]", className)} {...props} />
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className="rounded-xl border border-[var(--line)] bg-white/70 px-3 py-2.5 text-sm outline-none"
      {...props}
    />
  );
}
