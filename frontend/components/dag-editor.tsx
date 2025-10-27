"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { Play, Save, Undo, Redo, ZoomIn, ZoomOut, Database, Filter, GitMerge, FileOutput } from "lucide-react"

interface FunctionCard {
  id: string
  type: string
  label: string
  x: number
  y: number
  inputs: number
  outputs: number
}

interface Connection {
  from: string
  to: string
}

export function DAGEditor() {
  const [cards, setCards] = useState<FunctionCard[]>([
    { id: "1", type: "read", label: "Read CSV", x: 100, y: 150, inputs: 0, outputs: 1 },
    { id: "2", type: "filter", label: "Filter Rows", x: 350, y: 150, inputs: 1, outputs: 1 },
    { id: "3", type: "map", label: "Transform", x: 600, y: 100, inputs: 1, outputs: 1 },
    { id: "4", type: "join", label: "Join Data", x: 600, y: 250, inputs: 2, outputs: 1 },
    { id: "5", type: "write", label: "Write Output", x: 850, y: 180, inputs: 1, outputs: 0 },
  ])

  const [connections] = useState<Connection[]>([
    { from: "1", to: "2" },
    { from: "2", to: "3" },
    { from: "2", to: "4" },
    { from: "3", to: "4" },
    { from: "4", to: "5" },
  ])

  const getCardIcon = (type: string) => {
    switch (type) {
      case "read":
        return <Database className="w-4 h-4" />
      case "filter":
        return <Filter className="w-4 h-4" />
      case "join":
        return <GitMerge className="w-4 h-4" />
      case "write":
        return <FileOutput className="w-4 h-4" />
      default:
        return <Database className="w-4 h-4" />
    }
  }

  const getCardColor = (type: string) => {
    switch (type) {
      case "read":
        return "border-primary bg-primary/5"
      case "filter":
        return "border-accent bg-accent/5"
      case "map":
        return "border-chart-3 bg-chart-3/5"
      case "join":
        return "border-chart-4 bg-chart-4/5"
      case "write":
        return "border-chart-5 bg-chart-5/5"
      default:
        return "border-border bg-card"
    }
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <PageHeader
        title="DAG Editor"
        subtitle="data-pipeline-v1"
        rightContent={
          <>
            <Button variant="ghost" size="sm">
              <Undo className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="sm">
              <Redo className="w-4 h-4" />
            </Button>
            <div className="h-6 w-px bg-border mx-2" />
            <Button variant="ghost" size="sm">
              <ZoomOut className="w-4 h-4" />
            </Button>
            <span className="text-sm text-muted-foreground min-w-12 text-center">100%</span>
            <Button variant="ghost" size="sm">
              <ZoomIn className="w-4 h-4" />
            </Button>
            <div className="h-6 w-px bg-border mx-2" />
            <Button variant="outline" size="sm">
              <Save className="w-4 h-4 mr-2" />
              Save
            </Button>
            <Button size="sm" className="bg-primary text-primary-foreground">
              <Play className="w-4 h-4 mr-2" />
              Run
            </Button>
          </>
        }
      />

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar - Card Palette */}
        <aside className="w-64 border-r border-border bg-card p-4 overflow-y-auto">
          <h2 className="text-sm font-semibold text-foreground mb-4">Function Cards</h2>

          <div className="space-y-2">
            {[
              { type: "read", label: "Read Data", icon: Database, color: "primary" },
              { type: "filter", label: "Filter", icon: Filter, color: "accent" },
              { type: "map", label: "Map/Transform", icon: Database, color: "chart-3" },
              { type: "join", label: "Join", icon: GitMerge, color: "chart-4" },
              { type: "write", label: "Write Output", icon: FileOutput, color: "chart-5" },
            ].map((item) => (
              <Card key={item.type} className={`p-3 cursor-move hover:border-${item.color} transition-colors`}>
                <div className="flex items-center gap-2">
                  <div className={`w-8 h-8 rounded bg-${item.color}/10 flex items-center justify-center`}>
                    <item.icon className={`w-4 h-4 text-${item.color}`} />
                  </div>
                  <span className="text-sm text-card-foreground">{item.label}</span>
                </div>
              </Card>
            ))}
          </div>

          <div className="mt-6 pt-6 border-t border-border">
            <h3 className="text-xs font-semibold text-muted-foreground mb-3">TIPS</h3>
            <ul className="text-xs text-muted-foreground space-y-2">
              <li>• Drag cards to canvas</li>
              <li>• Click outputs to connect</li>
              <li>• Double-click to configure</li>
            </ul>
          </div>
        </aside>

        {/* Canvas */}
        <main className="flex-1 relative overflow-hidden bg-background">
          {/* Grid background */}
          <div
            className="absolute inset-0"
            style={{
              backgroundImage: `
                linear-gradient(to right, oklch(0.2 0 0) 1px, transparent 1px),
                linear-gradient(to bottom, oklch(0.2 0 0) 1px, transparent 1px)
              `,
              backgroundSize: "20px 20px",
            }}
          />

          {/* SVG for connections */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            <defs>
              <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
                <polygon points="0 0, 10 3, 0 6" fill="oklch(0.65 0.2 240)" opacity="0.6" />
              </marker>
            </defs>
            {connections.map((conn, idx) => {
              const fromCard = cards.find((c) => c.id === conn.from)
              const toCard = cards.find((c) => c.id === conn.to)
              if (!fromCard || !toCard) return null

              const x1 = fromCard.x + 120
              const y1 = fromCard.y + 40
              const x2 = toCard.x
              const y2 = toCard.y + 40

              const midX = (x1 + x2) / 2

              return (
                <path
                  key={idx}
                  d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                  stroke="oklch(0.65 0.2 240)"
                  strokeWidth="2"
                  fill="none"
                  opacity="0.6"
                  markerEnd="url(#arrowhead)"
                />
              )
            })}
          </svg>

          {/* Cards */}
          <div className="absolute inset-0">
            {cards.map((card) => (
              <div key={card.id} className="absolute" style={{ left: card.x, top: card.y }}>
                <Card className={`w-32 p-3 cursor-move hover:shadow-lg transition-shadow ${getCardColor(card.type)}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-6 h-6 rounded bg-background/50 flex items-center justify-center">
                      {getCardIcon(card.type)}
                    </div>
                    <span className="text-xs font-medium text-card-foreground">{card.label}</span>
                  </div>

                  {/* Input/Output ports */}
                  <div className="flex justify-between items-center mt-2">
                    {card.inputs > 0 && <div className="w-2 h-2 rounded-full bg-primary -ml-4" />}
                    {card.outputs > 0 && <div className="w-2 h-2 rounded-full bg-primary -mr-4 ml-auto" />}
                  </div>
                </Card>
              </div>
            ))}
          </div>
        </main>

        {/* Properties Panel */}
        <aside className="w-80 border-l border-border bg-card p-4 overflow-y-auto">
          <h2 className="text-sm font-semibold text-foreground mb-4">Properties</h2>

          <div className="space-y-4">
            <div>
              <label className="text-xs text-muted-foreground">Selected Card</label>
              <p className="text-sm text-foreground mt-1">Filter Rows</p>
            </div>

            <div>
              <label className="text-xs text-muted-foreground">Type</label>
              <p className="text-sm text-foreground mt-1">filter</p>
            </div>

            <div>
              <label className="text-xs text-muted-foreground mb-2 block">Configuration</label>
              <Card className="p-3 bg-background">
                <pre className="text-xs text-muted-foreground font-mono">
                  {`{
  "condition": "age > 18",
  "columns": ["name", "age"]
}`}
                </pre>
              </Card>
            </div>

            <div>
              <label className="text-xs text-muted-foreground">Inputs</label>
              <p className="text-sm text-foreground mt-1">1 connection</p>
            </div>

            <div>
              <label className="text-xs text-muted-foreground">Outputs</label>
              <p className="text-sm text-foreground mt-1">2 connections</p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
