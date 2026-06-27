/**
 * Supabase API Service for Media Monitoring Dashboard
 * Handles all database operations dengan Supabase
 */

import { createClient } from '@supabase/supabase-js'

// Initialize Supabase Client
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// ===================================
// Type Definitions
// ===================================

export interface NewsSource {
  id: number
  name: string
  slug: string
  url: string
  category: string
  is_active: boolean
  created_at: string
}

export interface Mention {
  id: number
  title: string
  content?: string
  source_id: number
  author?: string
  url?: string
  sentiment: 'positif' | 'negatif' | 'netral'
  mention_date: string
  created_at: string
  updated_at: string
  news_sources?: NewsSource
}

export interface Keyword {
  id: number
  keyword: string
  category: string
  is_active: boolean
  created_at: string
}

export interface SummaryData {
  total_mentions: number
  unique_authors: number
  sentiment: {
    positif: number
    negatif: number
    netral: number
  }
}

export interface TimelineItem {
  date: string
  count: number
}

export interface TopAuthor {
  author: string
  count: number
  avg_sentiment?: number
}

export interface SentimentBreakdownData {
  breakdown: {
    positif: Mention[]
    negatif: Mention[]
    netral: Mention[]
  }
  counts: {
    positif: number
    negatif: number
    netral: number
  }
}

// ===================================
// Data Fetching Functions
// ===================================

/**
 * Get summary statistics
 * Menggunakan stored procedure atau query aggregation
 */
export async function getSummary(): Promise<SummaryData> {
  try {
    // Get total mentions
    const { count: totalCount } = await supabase
      .from('mentions')
      .select('*', { count: 'exact', head: true })

    // Get unique authors
    const { data: authors } = await supabase
      .from('mentions')
      .select('author')
      .not('author', 'is', null)

    const uniqueAuthors = new Set(authors?.map(m => m.author)).size

    // Get sentiment breakdown
    const { data: sentiments } = await supabase
      .from('mentions')
      .select('sentiment')

    const sentimentCounts = {
      positif: sentiments?.filter(s => s.sentiment === 'positif').length || 0,
      negatif: sentiments?.filter(s => s.sentiment === 'negatif').length || 0,
      netral: sentiments?.filter(s => s.sentiment === 'netral').length || 0,
    }

    return {
      total_mentions: totalCount || 0,
      unique_authors: uniqueAuthors,
      sentiment: sentimentCounts,
    }
  } catch (error) {
    console.error('Error fetching summary:', error)
    throw error
  }
}

/**
 * Get mentions timeline (grouped by date)
 */
export async function getTimeline(): Promise<{ timeline: TimelineItem[] }> {
  try {
    const { data, error } = await supabase
      .from('mentions')
      .select('mention_date')
      .order('mention_date', { ascending: false })

    if (error) throw error

    // Group by date
    const timelineMap = new Map<string, number>()
    data?.forEach((mention) => {
      const date = mention.mention_date.split('T')[0] // YYYY-MM-DD
      timelineMap.set(date, (timelineMap.get(date) || 0) + 1)
    })

    const timeline = Array.from(timelineMap.entries())
      .sort(([dateA], [dateB]) => dateB.localeCompare(dateA))
      .map(([date, count]) => ({ date, count }))

    return { timeline }
  } catch (error) {
    console.error('Error fetching timeline:', error)
    throw error
  }
}

/**
 * Get top authors
 */
export async function getTopAuthors(): Promise<{ top_authors: TopAuthor[] }> {
  try {
    const { data, error } = await supabase
      .from('mentions')
      .select('author, sentiment')
      .not('author', 'is', null)
      .order('author')

    if (error) throw error

    // Group and count by author
    const authorMap = new Map<string, { count: number; sentiments: string[] }>()
    data?.forEach((mention) => {
      if (!authorMap.has(mention.author)) {
        authorMap.set(mention.author, { count: 0, sentiments: [] })
      }
      const entry = authorMap.get(mention.author)!
      entry.count += 1
      entry.sentiments.push(mention.sentiment)
    })

    const topAuthors = Array.from(authorMap.entries())
      .map(([author, { count, sentiments }]) => {
        const sentimentScore = sentiments.reduce((sum, s) => {
          return sum + (s === 'positif' ? 1 : s === 'negatif' ? -1 : 0)
        }, 0) / sentiments.length
        return {
          author,
          count,
          avg_sentiment: Math.round(sentimentScore * 100) / 100,
        }
      })
      .sort((a, b) => b.count - a.count)
      .slice(0, 10)

    return { top_authors: topAuthors }
  } catch (error) {
    console.error('Error fetching top authors:', error)
    throw error
  }
}

/**
 * Get word cloud data (most mentioned keywords)
 */
export async function getWordCloud(): Promise<{ wordcloud: { text: string; value: number }[] }> {
  try {
    const { data, error } = await supabase
      .from('keywords')
      .select(`
        keyword,
        mention_keywords(count)
      `)
      .eq('is_active', true)

    if (error) throw error

    const wordcloud = (data || [])
      .map((k) => ({
        text: k.keyword,
        value: k.mention_keywords?.length || 0,
      }))
      .filter(item => item.value > 0)
      .sort((a, b) => b.value - a.value)
      .slice(0, 50)

    return { wordcloud }
  } catch (error) {
    console.error('Error fetching word cloud:', error)
    throw error
  }
}

/**
 * Get all mentions with optional filtering
 */
export async function getMentions(
  limit: number = 50,
  offset: number = 0,
  sentiment?: string
): Promise<{ mentions: Mention[] }> {
  try {
    let query = supabase
      .from('mentions')
      .select(`
        *,
        news_sources (
          id,
          name,
          slug,
          url,
          category
        )
      `)

    if (sentiment) {
      query = query.eq('sentiment', sentiment)
    }

    const { data, error } = await query
      .order('mention_date', { ascending: false })
      .range(offset, offset + limit - 1)

    if (error) throw error

    return { mentions: data || [] }
  } catch (error) {
    console.error('Error fetching mentions:', error)
    throw error
  }
}

/**
 * Get sentiment breakdown
 */
export async function getSentimentBreakdown(): Promise<SentimentBreakdownData> {
  try {
    const { data, error } = await supabase
      .from('mentions')
      .select(`
        *,
        news_sources (
          id,
          name,
          slug,
          url,
          category
        )
      `)
      .order('mention_date', { ascending: false })

    if (error) throw error

    const breakdown = {
      positif: (data || []).filter(m => m.sentiment === 'positif'),
      negatif: (data || []).filter(m => m.sentiment === 'negatif'),
      netral: (data || []).filter(m => m.sentiment === 'netral'),
    }

    const counts = {
      positif: breakdown.positif.length,
      negatif: breakdown.negatif.length,
      netral: breakdown.netral.length,
    }

    return { breakdown, counts }
  } catch (error) {
    console.error('Error fetching sentiment breakdown:', error)
    throw error
  }
}

/**
 * Get mentions by source
 */
export async function getMentionsBySource(sourceId: number): Promise<{ mentions: Mention[] }> {
  try {
    const { data, error } = await supabase
      .from('mentions')
      .select(`
        *,
        news_sources (
          id,
          name,
          slug,
          url,
          category
        )
      `)
      .eq('source_id', sourceId)
      .order('mention_date', { ascending: false })

    if (error) throw error

    return { mentions: data || [] }
  } catch (error) {
    console.error('Error fetching mentions by source:', error)
    throw error
  }
}

/**
 * Get all news sources
 */
export async function getNewsSources(): Promise<NewsSource[]> {
  try {
    const { data, error } = await supabase
      .from('news_sources')
      .select('*')
      .eq('is_active', true)
      .order('name')

    if (error) throw error

    return data || []
  } catch (error) {
    console.error('Error fetching news sources:', error)
    throw error
  }
}

/**
 * Get all keywords
 */
export async function getKeywords(): Promise<Keyword[]> {
  try {
    const { data, error } = await supabase
      .from('keywords')
      .select('*')
      .eq('is_active', true)
      .order('keyword')

    if (error) throw error

    return data || []
  } catch (error) {
    console.error('Error fetching keywords:', error)
    throw error
  }
}

// ===================================
// Real-time Subscriptions (Optional)
// ===================================

/**
 * Subscribe to mention changes
 */
export function subscribeToMentions(callback: (mention: Mention) => void) {
  const subscription = supabase
    .channel('mentions-channel')
    .on(
      'postgres_changes',
      {
        event: '*',
        schema: 'public',
        table: 'mentions',
      },
      (payload) => {
        callback(payload.new as Mention)
      }
    )
    .subscribe()

  return subscription
}

// ===================================
// Export all APIs
// ===================================

export const supabaseApi = {
  getSummary,
  getTimeline,
  getTopAuthors,
  getWordCloud,
  getMentions,
  getSentimentBreakdown,
  getMentionsBySource,
  getNewsSources,
  getKeywords,
  subscribeToMentions,
}
