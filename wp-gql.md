curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query GetArticles($first: Int!, $after: String) {
      posts(first: 100, after: null, where: { status: PUBLISH }) {
        edges {
          node {
            __typename
            id
            title(format: RAW)
            slug
            date
            content(format: RAW)
            excerpt(format: RAW)
            uri
            author {
              node {
                name
                id
              }
            }
            categories {
              edges {
                node {
                  name
                  slug
                }
              }
            }
            featuredImage {
              node {
                id
                sourceUrl
                altText
                mediaDetails {
                  width
                  height
                  file
                }
                mediaType
                mimeType
              }
            }
            tags {
              edges {
                node {
                  name
                }
              }
            }
            seo {
              title
              metaDesc
              twitterDescription
              opengraphDescription
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }"
  }' \
  https://cybernow.info/graphql