import { Mascot, type MascotMood } from "@/components/mascot/Mascot";
import { cn } from "@/lib/cn";

export function LogoMark({
  className,
  mood,
  still,
  interactive,
}: {
  className?: string;
  mood?: MascotMood;
  still?: boolean;
  interactive?: boolean;
}) {
  return <Mascot size="sm" mood={mood} still={still} interactive={interactive} className={className} />;
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark className="size-8" interactive />
      <span className="text-[0.9375rem] font-semibold tracking-tight text-fg">AI Developer Assistant</span>
    </span>
  );
}
