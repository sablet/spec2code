import Link from "next/link"
import { Database, Library, Activity } from "lucide-react"
import { Button } from "@/components/ui/button"

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="container mx-auto px-6 py-4">
          <h1 className="text-xl font-semibold text-foreground">Function Card System</h1>
        </div>
      </header>

      <main className="container mx-auto px-6 py-12">
        <div className="mb-12">
          <h2 className="text-4xl font-bold text-foreground mb-4">Build Data Pipelines Visually</h2>
          <p className="text-lg text-muted-foreground max-w-2xl">
            Create complex data workflows by connecting function cards in a visual DAG editor.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Link href="/dag-editor" className="group">
            <div className="bg-card border border-border rounded-lg p-6 hover:border-primary transition-colors">
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                <Database className="w-6 h-6 text-primary" />
              </div>
              <h3 className="text-xl font-semibold text-card-foreground mb-2">DAG Editor</h3>
              <p className="text-muted-foreground mb-4">
                Visual editor for building data pipelines with drag-and-drop cards
              </p>
              <Button variant="ghost" className="text-primary group-hover:translate-x-1 transition-transform">
                Open Editor →
              </Button>
            </div>
          </Link>

          <Link href="/card-library" className="group">
            <div className="bg-card border border-border rounded-lg p-6 hover:border-accent transition-colors">
              <div className="w-12 h-12 rounded-lg bg-accent/10 flex items-center justify-center mb-4">
                <Library className="w-6 h-6 text-accent" />
              </div>
              <h3 className="text-xl font-semibold text-card-foreground mb-2">Card Library</h3>
              <p className="text-muted-foreground mb-4">
                Browse and preview available function cards for your pipelines
              </p>
              <Button variant="ghost" className="text-accent group-hover:translate-x-1 transition-transform">
                View Library →
              </Button>
            </div>
          </Link>

          <Link href="/execution-dashboard" className="group">
            <div className="bg-card border border-border rounded-lg p-6 hover:border-chart-3 transition-colors">
              <div className="w-12 h-12 rounded-lg bg-chart-3/10 flex items-center justify-center mb-4">
                <Activity className="w-6 h-6 text-chart-3" />
              </div>
              <h3 className="text-xl font-semibold text-card-foreground mb-2">Execution Dashboard</h3>
              <p className="text-muted-foreground mb-4">Monitor pipeline execution, metrics, and logs in real-time</p>
              <Button variant="ghost" className="text-chart-3 group-hover:translate-x-1 transition-transform">
                View Dashboard →
              </Button>
            </div>
          </Link>
        </div>
      </main>
    </div>
  )
}
