"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  ArrowLeft,
  Play,
  Pause,
  RotateCcw,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ChevronRight,
} from "lucide-react"
import Link from "next/link"

interface ExecutionLog {
  timestamp: string
  level: "info" | "warning" | "error"
  message: string
  cardId?: string
}

interface CardExecution {
  id: string
  name: string
  status: "pending" | "running" | "completed" | "failed"
  duration: number
  rowsProcessed: number
}

export function ExecutionDashboard() {
  const [selectedExecution, setSelectedExecution] = useState<string>("exec-001")

  const executions = [
    {
      id: "exec-001",
      name: "data-pipeline-v1",
      status: "running",
      startTime: "2025-01-10 14:32:15",
      duration: "2m 34s",
    },
    {
      id: "exec-002",
      name: "data-pipeline-v1",
      status: "completed",
      startTime: "2025-01-10 14:15:42",
      duration: "3m 12s",
    },
    {
      id: "exec-003",
      name: "data-pipeline-v1",
      status: "failed",
      startTime: "2025-01-10 13:58:21",
      duration: "1m 45s",
    },
  ]

  const cardExecutions: CardExecution[] = [
    { id: "1", name: "Read CSV", status: "completed", duration: 1.2, rowsProcessed: 10000 },
    { id: "2", name: "Filter Rows", status: "completed", duration: 0.8, rowsProcessed: 8500 },
    { id: "3", name: "Transform", status: "running", duration: 2.1, rowsProcessed: 5200 },
    { id: "4", name: "Join Data", status: "pending", duration: 0, rowsProcessed: 0 },
    { id: "5", name: "Write Output", status: "pending", duration: 0, rowsProcessed: 0 },
  ]

  const logs: ExecutionLog[] = [
    { timestamp: "14:32:15", level: "info", message: "Pipeline execution started", cardId: undefined },
    { timestamp: "14:32:16", level: "info", message: "Reading CSV file: data/input.csv", cardId: "1" },
    { timestamp: "14:32:17", level: "info", message: "Loaded 10,000 rows successfully", cardId: "1" },
    { timestamp: "14:32:18", level: "info", message: "Applying filter condition: age > 18", cardId: "2" },
    { timestamp: "14:32:19", level: "info", message: "Filtered to 8,500 rows", cardId: "2" },
    { timestamp: "14:32:20", level: "info", message: "Starting transformation", cardId: "3" },
    { timestamp: "14:32:22", level: "warning", message: 'Null value encountered in column "email"', cardId: "3" },
    { timestamp: "14:32:24", level: "info", message: "Processed 5,200 rows so far...", cardId: "3" },
  ]

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="w-4 h-4 text-chart-3" />
      case "running":
        return <Clock className="w-4 h-4 text-primary animate-spin" />
      case "failed":
        return <XCircle className="w-4 h-4 text-destructive" />
      case "pending":
        return <AlertCircle className="w-4 h-4 text-muted-foreground" />
      default:
        return null
    }
  }

  const getStatusBadge = (status: string) => {
    const variants: Record<string, any> = {
      completed: "default",
      running: "secondary",
      failed: "destructive",
      pending: "outline",
    }
    return (
      <Badge variant={variants[status]} className="capitalize">
        {status}
      </Badge>
    )
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back
              </Button>
            </Link>
            <div className="h-6 w-px bg-border" />
            <h1 className="text-lg font-semibold text-foreground">Execution Dashboard</h1>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">
              <Pause className="w-4 h-4 mr-2" />
              Pause
            </Button>
            <Button variant="outline" size="sm">
              <RotateCcw className="w-4 h-4 mr-2" />
              Restart
            </Button>
            <Button size="sm" className="bg-primary text-primary-foreground">
              <Play className="w-4 h-4 mr-2" />
              Run New
            </Button>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar - Execution History */}
        <aside className="w-80 border-r border-border bg-card p-4 overflow-y-auto">
          <h2 className="text-sm font-semibold text-foreground mb-4">Execution History</h2>

          <div className="space-y-2">
            {executions.map((exec) => (
              <Card
                key={exec.id}
                className={`p-3 cursor-pointer transition-colors ${
                  selectedExecution === exec.id ? "border-primary bg-primary/5" : "hover:bg-accent"
                }`}
                onClick={() => setSelectedExecution(exec.id)}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(exec.status)}
                    <span className="text-sm font-medium text-card-foreground">{exec.name}</span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                </div>
                <div className="text-xs text-muted-foreground space-y-1">
                  <div>{exec.startTime}</div>
                  <div className="flex items-center justify-between">
                    <span>Duration: {exec.duration}</span>
                    {getStatusBadge(exec.status)}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Metrics */}
          <div className="border-b border-border bg-card p-6">
            <div className="grid grid-cols-4 gap-6">
              <div>
                <div className="text-xs text-muted-foreground mb-1">Status</div>
                <div className="flex items-center gap-2">
                  <Clock className="w-5 h-5 text-primary animate-spin" />
                  <span className="text-2xl font-bold text-foreground">Running</span>
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Duration</div>
                <div className="text-2xl font-bold text-foreground">2m 34s</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Cards Completed</div>
                <div className="text-2xl font-bold text-foreground">2 / 5</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Rows Processed</div>
                <div className="text-2xl font-bold text-foreground">8,500</div>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="mt-6">
              <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
                <span>Overall Progress</span>
                <span>40%</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: "40%" }} />
              </div>
            </div>
          </div>

          {/* Card Execution Status */}
          <div className="flex-1 overflow-y-auto p-6">
            <h2 className="text-lg font-semibold text-foreground mb-4">Card Execution Status</h2>

            <div className="space-y-3">
              {cardExecutions.map((card) => (
                <Card key={card.id} className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 flex-1">
                      {getStatusIcon(card.status)}
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium text-card-foreground">{card.name}</span>
                          {getStatusBadge(card.status)}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {card.status === "completed" &&
                            `Processed ${card.rowsProcessed.toLocaleString()} rows in ${card.duration}s`}
                          {card.status === "running" &&
                            `Processing... ${card.rowsProcessed.toLocaleString()} rows so far`}
                          {card.status === "pending" && "Waiting for upstream cards to complete"}
                        </div>
                      </div>
                    </div>

                    {card.status === "running" && (
                      <div className="w-32">
                        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                          <div className="h-full bg-primary rounded-full animate-pulse" style={{ width: "60%" }} />
                        </div>
                      </div>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          </div>
        </main>

        {/* Logs Panel */}
        <aside className="w-96 border-l border-border bg-card flex flex-col overflow-hidden">
          <div className="p-4 border-b border-border">
            <h2 className="text-sm font-semibold text-foreground">Execution Logs</h2>
          </div>

          <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-2">
            {logs.map((log, idx) => (
              <div key={idx} className="flex gap-2">
                <span className="text-muted-foreground flex-shrink-0">{log.timestamp}</span>
                <span
                  className={`flex-shrink-0 ${
                    log.level === "error"
                      ? "text-destructive"
                      : log.level === "warning"
                        ? "text-chart-4"
                        : "text-chart-3"
                  }`}
                >
                  [{log.level.toUpperCase()}]
                </span>
                <span className="text-foreground break-words">{log.message}</span>
              </div>
            ))}
          </div>

          <div className="p-4 border-t border-border">
            <Button variant="outline" size="sm" className="w-full bg-transparent">
              Export Logs
            </Button>
          </div>
        </aside>
      </div>
    </div>
  )
}
