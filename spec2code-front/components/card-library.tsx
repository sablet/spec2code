"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft, Search, Shuffle, Upload, CheckCircle, FileType, FileText, Workflow } from "lucide-react"
import Link from "next/link"

interface CardDefinition {
  id: string
  name: string
  category: string
  description: string
  source_spec: string
  icon: any
  color: string
  // checks用
  target_dtype?: string
  implementation?: string
  // dtype用
  schema?: any
  example_id?: string
  check_ids?: string[]
  // example用
  dtype?: string
  data?: any
  // transform用
  params?: Record<string, any>
  input_dtype?: string
  output_dtype?: string
  // dag用
  stage_id?: string
  selection_mode?: string
  candidates?: string[]
}

interface SpecMetadata {
  source_file: string
  spec_name: string
  version: string
  description: string
}

const defaultCards: CardDefinition[] = [
  {
    id: "check_example",
    name: "check_example",
    category: "checks",
    description: "Example check function for data validation",
    source_spec: "default",
    icon: CheckCircle,
    color: "chart-1",
    target_dtype: "ExampleFrame",
    implementation: "checks/check_example.py",
  },
  {
    id: "ExampleFrame",
    name: "ExampleFrame",
    category: "dtype",
    description: "Example data type definition",
    source_spec: "default",
    icon: FileType,
    color: "chart-2",
    schema: { id: "int", name: "str", value: "float" },
    example_id: "example_data",
    check_ids: ["check_example"],
  },
  {
    id: "example_data",
    name: "example_data",
    category: "example",
    description: "Sample data for ExampleFrame",
    source_spec: "default",
    icon: FileText,
    color: "chart-3",
    dtype: "ExampleFrame",
    data: [{ id: 1, name: "test", value: 100.0 }],
  },
  {
    id: "transform_example",
    name: "transform_example",
    category: "transform",
    description: "Example transformation function",
    source_spec: "default",
    icon: Shuffle,
    color: "chart-4",
    params: { threshold: 0.5, mode: "strict" },
    input_dtype: "ExampleFrame",
    output_dtype: "ProcessedFrame",
    implementation: "transforms/transform_example.py",
  },
  {
    id: "stage_1",
    name: "stage_1",
    category: "dag",
    description: "First stage of the pipeline",
    source_spec: "default",
    icon: Workflow,
    color: "chart-5",
    stage_id: "stage_1",
    selection_mode: "single",
    candidates: ["transform_example", "transform_alternative"],
  },
]

function convertJsonToCards(jsonData: any): CardDefinition[] {
  const cards: CardDefinition[] = []

  const iconMap: Record<string, any> = {
    "checks": CheckCircle,
    "dtype": FileType,
    "example": FileText,
    "transform": Shuffle,
    "dag": Workflow,
    "dag_stage": Workflow,
  }

  for (const card of jsonData.cards || []) {
    const icon = iconMap[card.category] || FileType
    const metadata = card.metadata || {}

    cards.push({
      id: card.id,
      name: card.name,
      category: card.category,
      description: card.description,
      source_spec: card.source_spec || "unknown",
      icon,
      color: `chart-${(cards.length % 5) + 1}` as any,
      // checks
      target_dtype: metadata.target_dtype,
      implementation: metadata.impl || metadata.implementation,
      // dtype
      schema: metadata.type_details,
      check_ids: metadata.check_ids || [],
      example_id: metadata.example_id,
      // example
      data: metadata.input || metadata.data,
      // transform
      params: metadata.parameters,
      input_dtype: metadata.input_type,
      output_dtype: metadata.output_type,
      // dag
      stage_id: card.id,
      selection_mode: metadata.selection_mode,
      candidates: metadata.candidates || [metadata.from, metadata.to].filter(Boolean),
    })
  }

  return cards
}

export function CardLibrary() {
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedCategory, setSelectedCategory] = useState<string>("All")
  const [selectedSpec, setSelectedSpec] = useState<string>("All")
  const [cardDefinitions, setCardDefinitions] = useState<CardDefinition[]>([])
  const [specsMetadata, setSpecsMetadata] = useState<SpecMetadata[]>([])
  const [selectedCard, setSelectedCard] = useState<CardDefinition | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Load unified JSON on mount
  useEffect(() => {
    fetch("/cards/all-cards.json")
      .then((res) => res.json())
      .then((data) => {
        const cards = convertJsonToCards(data)
        setCardDefinitions(cards)
        setSpecsMetadata(data.specs || [])
        if (cards.length > 0) {
          setSelectedCard(cards[0])
        }
        setIsLoading(false)
      })
      .catch((error) => {
        console.error("Failed to load cards:", error)
        setCardDefinitions(defaultCards)
        setSelectedCard(defaultCards[0])
        setIsLoading(false)
      })
  }, [])

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (e) => {
      const content = e.target?.result as string
      try {
        const jsonData = JSON.parse(content)
        const cards = convertJsonToCards(jsonData)
        if (cards.length > 0) {
          setCardDefinitions(cards)
          setSelectedCard(cards[0])
        }
      } catch (err) {
        console.error("Failed to parse JSON:", err)
      }
    }
    reader.readAsText(file)
  }

  const categories = ["All", ...Array.from(new Set(cardDefinitions.map((c) => c.category)))]
  const specs = ["All", ...Array.from(new Set(cardDefinitions.map((c) => c.source_spec)))]

  const filteredCards = cardDefinitions.filter((card) => {
    const matchesSearch =
      card.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      card.description.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesCategory = selectedCategory === "All" || card.category === selectedCategory
    const matchesSpec = selectedSpec === "All" || card.source_spec === selectedSpec
    return matchesSearch && matchesCategory && matchesSpec
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-muted-foreground">Loading cards...</div>
      </div>
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
                戻る
              </Button>
            </Link>
            <div className="h-6 w-px bg-border" />
            <h1 className="text-lg font-semibold text-foreground">カードライブラリ</h1>
          </div>

          <div className="flex items-center gap-2">
            <label htmlFor="json-upload">
              <Button variant="outline" size="sm" asChild>
                <span className="cursor-pointer">
                  <Upload className="w-4 h-4 mr-2" />
                  JSONを読み込む
                </span>
              </Button>
            </label>
            <input id="json-upload" type="file" accept=".json" onChange={handleFileUpload} className="hidden" />

            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="カードを検索..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 w-64"
              />
            </div>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar - Categories & Specs */}
        <aside className="w-64 border-r border-border bg-card p-4 overflow-y-auto">
          <h2 className="text-sm font-semibold text-foreground mb-4">Spec</h2>

          <div className="space-y-1 mb-6">
            {specs.map((spec) => (
              <button
                key={spec}
                onClick={() => setSelectedSpec(spec)}
                className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                  selectedSpec === spec
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                }`}
              >
                <div className="truncate">{spec}</div>
                <span className="float-right text-xs">
                  {spec === "All"
                    ? cardDefinitions.length
                    : cardDefinitions.filter((c) => c.source_spec === spec).length}
                </span>
              </button>
            ))}
          </div>

          <div className="pt-6 border-t border-border">
            <h2 className="text-sm font-semibold text-foreground mb-4">カテゴリ</h2>

            <div className="space-y-1">
              {categories.map((category) => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                    selectedCategory === category
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  }`}
                >
                  {category}
                  <span className="float-right text-xs">
                    {category === "All"
                      ? cardDefinitions.length
                      : cardDefinitions.filter((c) => c.category === category).length}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="mt-6 pt-6 border-t border-border">
            <h3 className="text-xs font-semibold text-muted-foreground mb-3">統計</h3>
            <div className="space-y-2 text-xs text-muted-foreground">
              <div className="flex justify-between">
                <span>総カード数</span>
                <span className="text-foreground font-medium">{cardDefinitions.length}</span>
              </div>
              <div className="flex justify-between">
                <span>Spec数</span>
                <span className="text-foreground font-medium">{specs.length - 1}</span>
              </div>
              <div className="flex justify-between">
                <span>カテゴリ数</span>
                <span className="text-foreground font-medium">{categories.length - 1}</span>
              </div>
            </div>
          </div>
        </aside>

        {/* Main - Card Grid */}
        <main className="flex-1 p-6 overflow-y-auto">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-foreground mb-2">
              {selectedSpec !== "All" && selectedCategory !== "All"
                ? `${selectedSpec} - ${selectedCategory}カード`
                : selectedSpec !== "All"
                  ? `${selectedSpec}`
                  : selectedCategory !== "All"
                    ? `${selectedCategory}カード`
                    : "すべてのカード"}
            </h2>
            <p className="text-sm text-muted-foreground">{filteredCards.length}個のカードが利用可能</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredCards.map((card) => (
              <Card
                key={`${card.source_spec}-${card.id}`}
                className={`p-4 cursor-pointer transition-all hover:shadow-lg ${
                  selectedCard?.id === card.id && selectedCard?.source_spec === card.source_spec
                    ? `border-${card.color}`
                    : ""
                }`}
                onClick={() => setSelectedCard(card)}
              >
                <div className="flex items-start gap-3 mb-3">
                  <div
                    className={`w-10 h-10 rounded-lg bg-${card.color}/10 flex items-center justify-center flex-shrink-0`}
                  >
                    <card.icon className={`w-5 h-5 text-${card.color}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-card-foreground mb-1">{card.name}</h3>
                    <Badge variant="secondary" className="text-xs">
                      {card.category}
                    </Badge>
                  </div>
                </div>

                <p className="text-xs text-muted-foreground mb-3 line-clamp-2">{card.description}</p>

                <div className="text-xs text-muted-foreground space-y-1">
                  <div className="mb-2">
                    <Badge variant="outline" className="text-xs">
                      {card.source_spec}
                    </Badge>
                  </div>
                  {card.category === "checks" && card.target_dtype && <div>対象型: {card.target_dtype}</div>}
                  {card.category === "dtype" && card.schema && (
                    <div>フィールド数: {Object.keys(card.schema).length}</div>
                  )}
                  {card.category === "example" && card.dtype && <div>データ型: {card.dtype}</div>}
                  {card.category === "transform" && (
                    <div>
                      {card.input_dtype} → {card.output_dtype}
                    </div>
                  )}
                  {card.category === "dag" && card.selection_mode && <div>選択モード: {card.selection_mode}</div>}
                </div>
              </Card>
            ))}
          </div>
        </main>

        {/* Details Panel */}
        <aside className="w-96 border-l border-border bg-card p-6 overflow-y-auto">
          {selectedCard ? (
            <>
              <div className="flex items-start gap-4 mb-6">
                <div
                  className={`w-16 h-16 rounded-lg bg-${selectedCard.color}/10 flex items-center justify-center flex-shrink-0`}
                >
                  <selectedCard.icon className={`w-8 h-8 text-${selectedCard.color}`} />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-foreground mb-1">{selectedCard.name}</h2>
                  <div className="flex gap-2">
                    <Badge variant="secondary">{selectedCard.category}</Badge>
                    <Badge variant="outline">{selectedCard.source_spec}</Badge>
                  </div>
                </div>
              </div>

              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-foreground mb-2">説明</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{selectedCard.description}</p>
                </div>

                {selectedCard.category === "checks" && (
                  <>
                    {selectedCard.target_dtype && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">対象データ型</h3>
                        <Card className="p-3 bg-background">
                          <code className="text-xs font-mono text-foreground">{selectedCard.target_dtype}</code>
                        </Card>
                      </div>
                    )}
                    {selectedCard.implementation && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">実装パス</h3>
                        <Card className="p-3 bg-background">
                          <code className="text-xs font-mono text-foreground">{selectedCard.implementation}</code>
                        </Card>
                      </div>
                    )}
                  </>
                )}

                {selectedCard.category === "dtype" && (
                  <>
                    {selectedCard.schema && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">スキーマ</h3>
                        <Card className="p-3 bg-background">
                          <pre className="text-xs text-muted-foreground font-mono overflow-x-auto">
                            {JSON.stringify(selectedCard.schema, null, 2)}
                          </pre>
                        </Card>
                      </div>
                    )}
                    {selectedCard.example_id && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">サンプルデータID</h3>
                        <Card className="p-3 bg-background">
                          <code className="text-xs font-mono text-foreground">{selectedCard.example_id}</code>
                        </Card>
                      </div>
                    )}
                    {selectedCard.check_ids && selectedCard.check_ids.length > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">チェック関数</h3>
                        <div className="space-y-2">
                          {selectedCard.check_ids.map((check) => (
                            <Card key={check} className="p-3 bg-background">
                              <code className="text-xs font-mono text-foreground">{check}</code>
                            </Card>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}

                {selectedCard.category === "example" && (
                  <>
                    {selectedCard.dtype && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">データ型</h3>
                        <Card className="p-3 bg-background">
                          <code className="text-xs font-mono text-foreground">{selectedCard.dtype}</code>
                        </Card>
                      </div>
                    )}
                    {selectedCard.data && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">サンプルデータ</h3>
                        <Card className="p-3 bg-background">
                          <pre className="text-xs text-muted-foreground font-mono overflow-x-auto">
                            {JSON.stringify(selectedCard.data, null, 2)}
                          </pre>
                        </Card>
                      </div>
                    )}
                  </>
                )}

                {selectedCard.category === "transform" && (
                  <>
                    {selectedCard.params && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">パラメータ</h3>
                        <Card className="p-3 bg-background">
                          <pre className="text-xs text-muted-foreground font-mono overflow-x-auto">
                            {JSON.stringify(selectedCard.params, null, 2)}
                          </pre>
                        </Card>
                      </div>
                    )}
                    {selectedCard.input_dtype && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">入力データ型</h3>
                        <Card className="p-3 bg-background">
                          <code className="text-xs font-mono text-foreground">{selectedCard.input_dtype}</code>
                        </Card>
                      </div>
                    )}
                    {selectedCard.output_dtype && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">出力データ型</h3>
                        <Card className="p-3 bg-background">
                          <code className="text-xs font-mono text-foreground">{selectedCard.output_dtype}</code>
                        </Card>
                      </div>
                    )}
                    {selectedCard.implementation && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">実装パス</h3>
                        <Card className="p-3 bg-background">
                          <code className="text-xs font-mono text-foreground">{selectedCard.implementation}</code>
                        </Card>
                      </div>
                    )}
                  </>
                )}

                {selectedCard.category === "dag" && (
                  <>
                    {selectedCard.stage_id && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">ステージID</h3>
                        <Card className="p-3 bg-background">
                          <code className="text-xs font-mono text-foreground">{selectedCard.stage_id}</code>
                        </Card>
                      </div>
                    )}
                    {selectedCard.selection_mode && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">選択モード</h3>
                        <Card className="p-3 bg-background">
                          <code className="text-xs font-mono text-foreground">{selectedCard.selection_mode}</code>
                        </Card>
                      </div>
                    )}
                    {selectedCard.candidates && selectedCard.candidates.length > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold text-foreground mb-2">候補</h3>
                        <div className="space-y-2">
                          {selectedCard.candidates.map((candidate) => (
                            <Card key={candidate} className="p-3 bg-background">
                              <code className="text-xs font-mono text-foreground">{candidate}</code>
                            </Card>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}

                <Button className="w-full">キャンバスに追加</Button>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              カードを選択して詳細を表示
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
