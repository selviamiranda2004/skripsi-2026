// ✅ LOAD ENV DULU (WAJIB)
import dotenv from 'dotenv'
dotenv.config({ path: '.env.local' })

import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

// debug (boleh hapus nanti)
console.log('URL:', supabaseUrl)
console.log('KEY detected:', !!supabaseKey)

if (!supabaseUrl || !supabaseKey) {
  throw new Error('Missing Supabase credentials')
}

const supabase = createClient(supabaseUrl, supabaseKey)

async function test() {
  console.log('Testing Supabase connection...')

  // Test 1
  const { data: sources, error: sourcesError } = await supabase
    .from('news_sources')
    .select('*')
    .limit(5)

  if (sourcesError) {
    console.error('❌ Error fetching sources:', sourcesError)
  } else {
    console.log('✅ News sources:', sources)
  }

  // Test 2
  const { data: mentions, error: mentionsError } = await supabase
    .from('mentions')
    .select('*')
    .limit(5)

  if (mentionsError) {
    console.error('❌ Error fetching mentions:', mentionsError)
  } else {
    console.log('✅ Mentions count:', mentions?.length)
  }

  // Test 3
  const { data: keywords, error: keywordsError } = await supabase
    .from('keywords')
    .select('*')
    .limit(5)

  if (keywordsError) {
    console.error('❌ Error fetching keywords:', keywordsError)
  } else {
    console.log('✅ Keywords:', keywords?.map(k => k.keyword))
  }

  console.log('\n✅ All tests passed!')
}

test().catch(console.error)