import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import { ReactNode } from "react"

import { Button } from "@/components/ui/button"

interface PageHeaderProps {
  title: string
  subtitle?: string
  backHref?: string
  backLabel?: string
  rightContent?: ReactNode
}

export function PageHeader({
  title,
  subtitle,
  backHref = "/",
  backLabel = "Back",
  rightContent,
}: PageHeaderProps) {
  return (
    <header className="border-b border-border bg-card">
      <div className="px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href={backHref}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="w-4 h-4 mr-2" />
              {backLabel}
            </Button>
          </Link>
          <div className="h-6 w-px bg-border" />
          <h1 className="text-lg font-semibold text-foreground">{title}</h1>
          {subtitle ? <span className="text-sm text-muted-foreground">{subtitle}</span> : null}
        </div>

        {rightContent ? <div className="flex items-center gap-2">{rightContent}</div> : null}
      </div>
    </header>
  )
}
