export interface MilotoDrawListItem {
  game_id: number
  game_date: string
  numbers: number[]
  accumulated: string
  jackpot: boolean
}

export interface ResultDetails {
  prize_for_winner: number
  winners: number
}

export interface MilotoDraw {
  game_id: number
  game_date: string
  numbers: number[]
  accumulated: number
  combination_id: string
  hits_2: ResultDetails | null
  hits_3: ResultDetails | null
  hits_4: ResultDetails | null
  hits_5: ResultDetails | null
}
