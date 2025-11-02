# Frontend Development Guide
 

This guide teaches developers how to make backend requests in the Jobmate.Agent Next.js application. The system primarily uses Redux Toolkit Query (RTK Query) for API calls, with a few exceptions where direct fetch is used.

## Table of Contents

- [Setup & Installation](#setup--installation)
- [Running the Project](#running-the-project)
- [Introduction & Architecture](#introduction--architecture)
- [Redux Setup & Configuration](#redux-setup--configuration)
- [Using RTK Query (Primary Method)](#using-rtk-query-primary-method)
- [Creating New RTK Query Endpoints](#creating-new-rtk-query-endpoints)
- [Exceptions: When to Use Direct Fetch](#exceptions-when-to-use-direct-fetch)
- [Data Validation with Zod](#data-validation-with-zod)
- [Complete Examples](#complete-examples)
- [Best Practices](#best-practices)
- [Common Patterns](#common-patterns)
- [Troubleshooting](#troubleshooting)


## Setup & Installation

### Prerequisites

Before setting up the frontend, ensure you have the following installed:

- **Node.js** (version 18.0 or higher)
- **npm**, **yarn**, **pnpm**, or **bun** package manager
- **Git** for version control

### Package Installation

The frontend uses Next.js 15 with React 19 and requires several dependencies for state management, UI components, and API communication.

#### Install Dependencies

Navigate to the frontend directory and install all required packages:

```bash
cd frontend

# Using npm
npm install

# Using yarn
yarn install

# Using pnpm (recommended for better performance)
pnpm install

# Using bun
bun install
```

#### Key Dependencies Installed

The installation will include these essential packages:

**Core Framework:**
- `next` (15.5.5) - React framework
- `react` (19.1.0) - UI library
- `react-dom` (19.1.0) - DOM rendering

**State Management:**
- `@reduxjs/toolkit` (^2.9.2) - Redux state management
- `react-redux` (^9.2.0) - React bindings for Redux

**UI Components:**
- `@radix-ui/*` - Accessible UI primitives
- `lucide-react` (^0.546.0) - Icon library
- `tailwindcss` (^4) - CSS framework
- `framer-motion` (^12.23.24) - Animation library

**API & Data:**
- `axios` (^1.12.2) - HTTP client
- `zod` (^4.1.12) - Schema validation
- `@auth0/nextjs-auth0` (^4.11.0) - Authentication

**Development Tools:**
- `typescript` (^5) - Type checking
- `eslint` (^9) - Code linting
- `tsx` (^4.20.6) - TypeScript execution

### Environment Configuration

Create a `.env.local` file in the frontend directory with the following variables:

```bash
# frontend/.env.local

# Auth0 Configuration
AUTH0_SECRET='your-auth0-secret'
AUTH0_BASE_URL='http://localhost:3000'
AUTH0_ISSUER_BASE_URL='https://your-domain.auth0.com'
AUTH0_CLIENT_ID='your-auth0-client-id'
AUTH0_CLIENT_SECRET='your-auth0-client-secret'
AUTH0_AUDIENCE='your-auth0-audience'
AUTH0_SCOPE='openid profile email'

# Backend Configuration (Flask API base)
BACKEND_URL='http://127.0.0.1:5001'  # Next.js proxy forwards to `${BACKEND_URL}/api/*`

# Optional: Email Service (if using contact forms)
EMAILJS_SERVICE_ID='your-emailjs-service-id'
EMAILJS_TEMPLATE_ID='your-emailjs-template-id'
EMAILJS_PUBLIC_KEY='your-emailjs-public-key'
```

**Important:** Replace the placeholder values with your actual Auth0 and backend configuration.

## Running the Project

### Development Server

Start the development server with hot reloading:

```bash
# Using npm
npm run dev

# Using yarn
yarn dev

# Using pnpm
pnpm dev

# Using bun
bun dev
```

The development server will start on `http://localhost:3000` by default.

### Available Scripts

The project includes several npm scripts for different tasks:

```bash
# Development server with Turbopack (faster builds)
npm run dev

# Production build
npm run build

# Start production server
npm run start

# Run linting
npm run lint

# Run tests
npm run test
```

### Backend Requirements

The frontend requires a running Flask backend server. Ensure your backend is running on the configured `BACKEND_URL` (default: `http://127.0.0.1:5001`).

**Backend Setup:**
1. Navigate to the project root directory
2. Install Python dependencies: `pip install -r requirements.txt`
3. Start the Flask server: `python run.py`

### Development Workflow

1. **Start Backend**: Run the Flask server first
2. **Start Frontend**: Run the Next.js development server
3. **Access Application**: Open `http://localhost:3000` in your browser
4. **Authentication**: The app uses Auth0 for user authentication
5. **API Calls**: All backend requests are proxied through Next.js API routes

### Troubleshooting Installation

**Common Issues:**

1. **Node Version Compatibility**
   ```bash
   # Check Node version
   node --version
   
   # Should be 18.0 or higher
   # If not, update Node.js from https://nodejs.org
   ```

2. **Package Manager Issues**
   ```bash
   # Clear cache and reinstall
   npm cache clean --force
   rm -rf node_modules package-lock.json
   npm install
   ```

3. **Permission Errors (macOS/Linux)**
   ```bash
   # Fix npm permissions
   sudo chown -R $(whoami) ~/.npm
   ```

4. **Port Already in Use**
   ```bash
   # Kill process on port 3000
   lsof -ti:3000 | xargs kill -9
   
   # Or use a different port
   npm run dev -- -p 3001
   ```

### Production Build

To create a production build:

```bash
# Build the application
npm run build

# Start production server
npm run start
```

The production build will be optimized and minified for better performance.


## Introduction & Architecture

### Next.js API Proxy Pattern

The application uses a Next.js API route as a proxy to the Flask backend:

```typescript
// frontend/src/app/api/backend/[...path]/route.ts
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:5001";

async function proxy(req: NextRequest, path: string[]) {
  // Get Auth0 session and access token
  const session = await auth0.getSession();
  const tokenRes = await auth0.getAccessToken({
    refresh: true,
    audience: process.env.AUTH0_AUDIENCE,
    scope: process.env.AUTH0_SCOPE || "openid profile email",
  });
  
  const bearer = tokenRes?.accessToken ?? tokenRes?.token ?? undefined;
  
  // Forward request to Flask backend with authentication
  const targetUrl = `${BACKEND_URL}/api/${path.join("/")}${req.nextUrl.search}`;
  const upstream = await fetch(targetUrl, {
    method: req.method,
    headers: {
      ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}),
      ...(req.headers.get("content-type") ? { "content-type": req.headers.get("content-type") as string } : {}),
    },
    body: ["GET", "HEAD"].includes(req.method) ? undefined : await req.text(),
  });
  
  return new NextResponse(upstream.body, { status: upstream.status });
}
```

**Why this pattern?**
- **Authentication**: Auth0 tokens are automatically injected into backend requests
- **CORS**: Avoids CORS issues by proxying through Next.js
- **Environment**: Handles different backend URLs for dev/prod
- **Security**: Keeps backend credentials server-side

### Why RTK Query?

RTK Query is the primary method because it provides:
- **Automatic caching**: Reduces unnecessary network requests
- **Loading states**: Built-in loading/error/data states
- **Cache invalidation**: Automatic refetching when data changes
- **Type safety**: Full TypeScript support
- **Optimistic updates**: Immediate UI updates with rollback on failure

## Redux Setup & Configuration

### Store Configuration

The Redux store is configured with multiple API slices:

```typescript
// frontend/src/store/store.ts
import { configureStore } from '@reduxjs/toolkit';
import { jobsApi } from './jobsApi';
import { resumesApi } from './resumesApi';
import { profileApi } from './profileApi';
import { chatApi } from './chatApi';

export const store = configureStore({
  reducer: {
    [jobsApi.reducerPath]: jobsApi.reducer,
    [resumesApi.reducerPath]: resumesApi.reducer,
    [profileApi.reducerPath]: profileApi.reducer,
    [chatApi.reducerPath]: chatApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: ['persist/PERSIST', 'persist/REHYDRATE'],
      },
    }).concat(
      jobsApi.middleware,
      resumesApi.middleware,
      profileApi.middleware,
      chatApi.middleware
    ),
});
```

### Provider Setup

The Redux provider is configured in the root layout:

```typescript
// frontend/src/app/layout.tsx
import { ReduxProvider } from "@/store/provider";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ReduxProvider>
          <div className="min-h-dvh grid grid-rows-[auto_1fr]">
            <Navbar />
            <main>{children}</main>
          </div>
        </ReduxProvider>
      </body>
    </html>
  );
}
```

### Available API Slices

The system includes four main API slices:

1. **`jobsApi`** - Job listings, search, and management
2. **`resumesApi`** - Resume upload, management, and operations
3. **`profileApi`** - User contact information
4. **`chatApi`** - Chat sessions and messages (non-streaming)

## Using RTK Query (Primary Method)

### Importing Hooks

Each API slice exports typed hooks for queries and mutations:

```typescript
// From jobsApi
import { 
  useGetJobsQuery,
  useGetJobQuery,
  useSearchJobsQuery,
  useCreateJobMutation,
  useUpdateJobMutation,
  useDeleteJobMutation
} from '@/store/jobsApi';

// From resumesApi
import { 
  useGetResumesQuery,
  useUploadResumeMutation,
  useSetDefaultResumeMutation,
  useDeleteResumeMutation
} from '@/store/resumesApi';

// From profileApi
import { 
  useGetContactInfoQuery,
  useUpdateContactInfoMutation
} from '@/store/profileApi';

// From chatApi
import { 
  useGetChatsQuery,
  useGetChatMessagesQuery,
  useCreateChatMutation,
  useDeleteChatMutation
} from '@/store/chatApi';
```

### Query Hooks (GET Requests)

Query hooks automatically fetch data and provide loading states:

```typescript
function JobListings() {
  // Basic query
  const { data: jobs, error, isLoading } = useGetJobsQuery();
  
  // Query with filters
  const { data: filteredJobs } = useGetJobsQuery({
    page: 1,
    limit: 10,
    job_type: 'full-time',
    location: 'San Francisco'
  });
  
  // Search query
  const { data: searchResults } = useSearchJobsQuery({
    query: 'software engineer',
    page: 1,
    limit: 20
  });
  
  if (isLoading) return <div>Loading jobs...</div>;
  if (error) return <div>Error: {error.message}</div>;
  
  return (
    <div>
      {jobs?.jobs.map(job => (
        <div key={job.id}>
          <h3>{job.title}</h3>
          <p>{job.company} - {job.location}</p>
        </div>
      ))}
    </div>
  );
}
```

### Mutation Hooks (POST/PUT/DELETE)

Mutation hooks handle data modifications:

```typescript
function ResumeUploader() {
  const [uploadResume, { isLoading, error }] = useUploadResumeMutation();
  const [setDefaultResume] = useSetDefaultResumeMutation();
  
  const handleUpload = async (file: File) => {
    try {
      const formData = new FormData();
      // Backend expects multipart field name 'resume_file'
      formData.append('resume_file', file);
      
      const result = await uploadResume(formData).unwrap();
      console.log('Upload successful:', result);
    } catch (err) {
      console.error('Upload failed:', err);
    }
  };
  
  const handleSetDefault = async (resumeId: number) => {
    try {
      await setDefaultResume(resumeId).unwrap();
      console.log('Default resume updated');
    } catch (err) {
      console.error('Failed to set default:', err);
    }
  };
  
  return (
    <div>
      <input 
        type="file" 
        onChange={(e) => handleUpload(e.target.files?.[0])}
        disabled={isLoading}
      />
      {isLoading && <p>Uploading...</p>}
      {error && <p>Error: {error.message}</p>}
    </div>
  );
}
```

### Handling Loading, Data, and Error States

RTK Query provides comprehensive state management:

```typescript
function ProfileEditor() {
  const { 
    data: contactInfo, 
    error, 
    isLoading,
    isFetching,
    isSuccess,
    isError
  } = useGetContactInfoQuery();
  
  const [updateContactInfo, { 
    isLoading: isUpdating,
    error: updateError 
  }] = useUpdateContactInfoMutation();
  
  // Different loading states
  if (isLoading) return <div>Loading profile...</div>;
  if (isError) return <div>Error: {error.message}</div>;
  if (isFetching) return <div>Refreshing profile...</div>;
  
  return (
    <div>
      {contactInfo && (
        <form onSubmit={handleSubmit}>
          <input defaultValue={contactInfo.name} />
          <input defaultValue={contactInfo.email} />
          <button disabled={isUpdating}>
            {isUpdating ? 'Updating...' : 'Update Profile'}
          </button>
        </form>
      )}
      {updateError && <p>Update failed: {updateError.message}</p>}
    </div>
  );
}
```

### Automatic Caching and Cache Invalidation

RTK Query automatically caches responses and invalidates cache when data changes:

```typescript
// frontend/src/store/jobsApi.ts
export const jobsApi = createApi({
  // ... configuration
  tagTypes: ['Job'],
  endpoints: (builder) => ({
    getJobs: builder.query<JobsResponse, JobFilters | void>({
      query: (filters = {}) => {
        // ... query logic
      },
      providesTags: (result) =>
        result
          ? [
              ...result.jobs.map(({ id }) => ({ type: 'Job' as const, id })),
              { type: 'Job', id: 'LIST' },
            ]
          : [{ type: 'Job', id: 'LIST' }],
    }),
    
    createJob: builder.mutation<Job, Partial<Job>>({
      query: (jobData) => ({
        url: 'jobs',
        method: 'POST',
        body: jobData,
      }),
      // Invalidate cache when new job is created
      invalidatesTags: [{ type: 'Job', id: 'LIST' }],
    }),
  }),
});
```

**Cache Tags Explained:**
- `providesTags`: What data this endpoint provides
- `invalidatesTags`: What cache to invalidate when this mutation runs
- Automatic refetching occurs when cache is invalidated

## Creating New RTK Query Endpoints

### Step 1: Define Zod Schemas

First, define the response schema in `frontend/src/schemas/api.ts`:

```typescript
// frontend/src/schemas/api.ts
export const NewFeatureResponseSchema = z.object({
  id: z.number(),
  name: z.string(),
  description: z.string(),
  created_at: z.string(),
});

export const NewFeatureRequestSchema = z.object({
  name: z.string(),
  description: z.string(),
});

export type NewFeatureResponse = z.infer<typeof NewFeatureResponseSchema>;
export type NewFeatureRequest = z.infer<typeof NewFeatureRequestSchema>;
```

### Step 2: Export Types

Add the types to `frontend/src/types/api.ts`:

```typescript
// frontend/src/types/api.ts
export type {
  NewFeatureResponse,
  NewFeatureRequest,
} from '@/schemas/api';

export {
  NewFeatureResponseSchema,
  NewFeatureRequestSchema,
} from '@/schemas/api';
```

### Step 3: Create or Extend API Slice

Create a new API slice or add to an existing one:

```typescript
// frontend/src/store/newFeatureApi.ts
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { NewFeatureResponseSchema, NewFeatureRequestSchema } from '@/schemas/api';
import type { NewFeatureResponse, NewFeatureRequest } from '@/types/api';

export const newFeatureApi = createApi({
  reducerPath: 'newFeatureApi',
  baseQuery: fetchBaseQuery({
    baseUrl: '/api/backend/',
    prepareHeaders: (headers) => {
      headers.set('Accept', 'application/json');
      headers.set('Content-Type', 'application/json');
      return headers;
    },
  }),
  tagTypes: ['NewFeature'],
  endpoints: (builder) => ({
    // GET /api/backend/new-features
    getNewFeatures: builder.query<NewFeatureResponse[], void>({
      query: () => 'new-features',
      transformResponse: (response: unknown) => {
        try {
          return z.array(NewFeatureResponseSchema).parse(response);
        } catch (error) {
          console.error('New features response validation failed:', error);
          throw error;
        }
      },
      providesTags: (result) =>
        result
          ? result.map(({ id }) => ({ type: 'NewFeature' as const, id }))
          : [],
    }),
    
    // POST /api/backend/new-features
    createNewFeature: builder.mutation<NewFeatureResponse, NewFeatureRequest>({
      query: (featureData) => ({
        url: 'new-features',
        method: 'POST',
        body: featureData,
      }),
      transformResponse: (response: unknown) => {
        try {
          return NewFeatureResponseSchema.parse(response);
        } catch (error) {
          console.error('Create feature response validation failed:', error);
          throw error;
        }
      },
      invalidatesTags: [{ type: 'NewFeature', id: 'LIST' }],
    }),
  }),
});

// Export hooks
export const {
  useGetNewFeaturesQuery,
  useCreateNewFeatureMutation,
} = newFeatureApi;
```

### Step 4: Register in Store

Add the new API slice to the store configuration:

```typescript
// frontend/src/store/store.ts
import { newFeatureApi } from './newFeatureApi';

export const store = configureStore({
  reducer: {
    // ... existing reducers
    [newFeatureApi.reducerPath]: newFeatureApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      // ... existing middleware config
    }).concat(
      // ... existing middleware
      newFeatureApi.middleware
    ),
});
```

### Step 5: Use in Components

```typescript
function NewFeatureList() {
  const { data: features, isLoading, error } = useGetNewFeaturesQuery();
  const [createFeature, { isLoading: isCreating }] = useCreateNewFeatureMutation();
  
  const handleCreate = async (name: string, description: string) => {
    try {
      await createFeature({ name, description }).unwrap();
      // Cache automatically invalidates and refetches
    } catch (err) {
      console.error('Failed to create feature:', err);
    }
  };
  
  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;
  
  return (
    <div>
      {features?.map(feature => (
        <div key={feature.id}>
          <h3>{feature.name}</h3>
          <p>{feature.description}</p>
        </div>
      ))}
    </div>
  );
}
```

## Exceptions: When to Use Direct Fetch

While RTK Query is the primary method, there are three documented exceptions in the codebase:

### 1. Streaming Responses

RTK Query doesn't support streaming responses, so direct fetch is used for chat streaming:

```typescript
// frontend/src/app/chat_help/ChatClient.tsx
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  const text = input.trim();
  if (!text || sending) return;

  setSending(true);

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 25000);

    const resp = await fetch("/api/backend/chat/stream", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json", 
        Accept: "text/plain, application/json" 
      },
      body: JSON.stringify({ message: text, model, chat_id: currentChatId }),
      signal: controller.signal,
    });
    
    clearTimeout(timeout);

    if (!resp.ok || !resp.body) {
      throw new Error(`Upstream error: ${resp.status}`);
    }

    // Handle streaming response
    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    const updateLastAssistant = (chunk: string) => {
      buffer += chunk;
      setMessages((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i].role === "assistant") {
            next[i] = { ...next[i], content: buffer };
            break;
          }
        }
        return next;
      });
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      updateLastAssistant(chunk);
    }
  } catch (err) {
    console.error(err);
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: `⚠️ Error: ${(err as Error).message}` },
    ]);
  } finally {
    setSending(false);
  }
};
```

**When to use direct fetch for streaming:**
- Real-time chat responses
- Server-sent events
- WebSocket connections
- Large file downloads with progress

### 2. Testing/Debugging

Simple ping tests use Axios for debugging:

```typescript
// frontend/src/components/PingButton.tsx
import axios from 'axios';

export default function PingButton() {
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onClick = async () => {
    setLoading(true);
    setStatus(null);
    try {
      const res = await axios.get('/api/backend/ping-protected');
      setStatus(`${res.status} ${res.statusText}: ${JSON.stringify(res.data)}`);
    } catch (e) {
      if (axios.isAxiosError(e)) {
        setStatus(`Error: ${e.message}`);
      } else {
        const err = e as { message?: string };
        setStatus(`Error: ${err?.message ?? 'unknown error'}`);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-6 space-y-2">
      <Button onClick={onClick} disabled={loading} variant="outline">
        {loading ? 'Pinging…' : 'Ping Protected Backend'}
      </Button>
      {status && (
        <div className="text-xs text-brand-primary break-all text-left max-w-prose mx-auto font-sans">
          {status}
        </div>
      )}
    </div>
  );
}
```

**When to use Axios for testing:**
- Simple ping/health checks
- Debugging API connectivity
- Quick prototyping
- Non-production testing tools

### 3. Custom Fetch Logic in RTK Query

Sometimes you need custom fetch logic within RTK Query:

```typescript
// frontend/src/store/jobsApi.ts
export const jobsApi = createApi({
  reducerPath: 'jobsApi',
  baseQuery: fetchBaseQuery({
    baseUrl: '/api/backend/',
    prepareHeaders: (headers) => {
      console.log('🔧 RTK Query: Preparing headers for request');
      headers.set('Accept', 'application/json');
      console.log('📋 RTK Query: Headers prepared:', Object.fromEntries(headers.entries()));
      return headers;
    },
    // Custom fetch function for debugging
    fetchFn: async (input, init) => {
      console.log('🚀 RTK Query: Making fetch request');
      console.log('📍 URL:', input);
      console.log('⚙️ Options:', init);
      
      try {
        const response = await fetch(input, init);
        console.log('📨 RTK Query: Response received');
        console.log('📊 Status:', response.status, response.statusText);
        console.log('📋 Response Headers:', Object.fromEntries(response.headers.entries()));
        
        // Clone response to read body for logging without consuming the stream
        const clonedResponse = response.clone();
        const responseText = await clonedResponse.text();
        console.log('📄 Response Body (first 500 chars):', responseText.substring(0, 500));
        
        return response;
      } catch (error) {
        console.error('❌ RTK Query: Fetch error:', error);
        throw error;
      }
    },
  }),
  // ... rest of configuration
});
```

**When to use custom fetch logic:**
- Detailed request/response logging
- Custom error handling
- Request/response transformation
- Authentication token refresh

### Jobs API note

- Use the jobs endpoints under `/api/backend/jobs` for creating and managing job listings. There is no `job_target` alias route in the current API.

### Decision Matrix

| Use Case | Method | Reason |
|----------|--------|---------|
| Standard CRUD operations | RTK Query | Automatic caching, loading states |
| File uploads | RTK Query | FormData support, progress tracking |
| Real-time streaming | Direct fetch | RTK Query doesn't support streaming |
| Simple debugging | Axios | Easier error handling for tests |
| Custom request logic | RTK Query + custom fetchFn | Best of both worlds |

## Data Validation with Zod

### Schema Definition

All API responses are validated using Zod schemas:

```typescript
// frontend/src/schemas/api.ts
export const JobSchema = z.object({
  id: z.number(),
  title: z.string(),
  company: z.string(),
  location: z.string().optional(),
  job_type: z.string().optional(),
  description: z.string().optional(),
  requirements: z.string().nullable().optional(),
  salary_min: z.number().nullable().optional(),
  salary_max: z.number().nullable().optional(),
  salary_currency: z.string().optional(),
  external_url: z.string().optional(),
  external_id: z.string().optional(),
  source: z.string().optional(),
  company_logo_url: z.string().optional(),
  company_website: z.string().nullable().optional(),
  required_skills: z.array(z.string()).optional(),
  preferred_skills: z.array(z.string()).optional(),
  is_active: z.boolean().optional(),
  is_remote: z.boolean().optional(),
  date_posted: z.string().optional(),
  date_expires: z.string().nullable().optional(),
  created_at: z.string().optional(),
  updated_at: z.string().optional(),
  vector_doc_id: z.string().nullable().optional(),
});

export type Job = z.infer<typeof JobSchema>;
```

### Transform Response Pattern

API slices use `transformResponse` to validate responses:

```typescript
// frontend/src/store/jobsApi.ts
getJobs: builder.query<JobsResponse, JobFilters | void>({
  query: (filters = {}) => {
    // ... query logic
  },
  transformResponse: (response: unknown) => {
    try {
      return JobsResponseSchema.parse(response);
    } catch (error) {
      console.error('Jobs response validation failed:', error);
      if (error instanceof ZodError) {
        throw new Error(getZodErrorMessage(error));
      }
      throw error;
    }
  },
  // ... rest of configuration
}),
```

### Error Handling

Zod validation errors are handled gracefully:

```typescript
// frontend/src/lib/zodErrors.ts
import { ZodError } from 'zod';

export function getZodErrorMessage(error: ZodError): string {
  return error.errors
    .map(err => `${err.path.join('.')}: ${err.message}`)
    .join(', ');
}
```

**Benefits of Zod validation:**
- **Runtime safety**: Catches API contract violations
- **Type inference**: Automatic TypeScript types
- **Error messages**: Clear validation error details
- **Development**: Early detection of API changes

## Complete Examples

### Creating/Updating Profile Information

This example demonstrates a complete CRUD operation using RTK Query for user profile management:

```typescript
function ProfileEditor() {
  const { 
    data: contactInfo, 
    error: fetchError, 
    isLoading: isFetching 
  } = useGetContactInfoQuery();
  
  const [updateContactInfo, { 
    isLoading: isUpdating, 
    error: updateError 
  }] = useUpdateContactInfoMutation();
  
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone_number: '',
    location: ''
  });
  
  // Populate form when data loads
  useEffect(() => {
    if (contactInfo) {
      setFormData({
        name: contactInfo.name,
        email: contactInfo.email,
        phone_number: contactInfo.phone_number,
        location: contactInfo.location
      });
    }
  }, [contactInfo]);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      await updateContactInfo(formData).unwrap();
      console.log('Profile updated successfully');
    } catch (err) {
      console.error('Update failed:', err);
    }
  };
  
  const handleChange = (field: keyof typeof formData) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setFormData(prev => ({
      ...prev,
      [field]: e.target.value
    }));
  };
  
  if (isFetching) return <div>Loading profile...</div>;
  if (fetchError) return <div>Error: {fetchError.message}</div>;
  
  return (
    <form onSubmit={handleSubmit} className="profile-form">
      <div className="form-group">
        <label htmlFor="name">Name</label>
        <input
          id="name"
          type="text"
          value={formData.name}
          onChange={handleChange('name')}
          required
        />
      </div>
      
      <div className="form-group">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          value={formData.email}
          onChange={handleChange('email')}
          required
        />
      </div>
      
      <div className="form-group">
        <label htmlFor="phone">Phone Number</label>
        <input
          id="phone"
          type="tel"
          value={formData.phone_number}
          onChange={handleChange('phone_number')}
          required
        />
      </div>
      
      <div className="form-group">
        <label htmlFor="location">Location</label>
        <input
          id="location"
          type="text"
          value={formData.location}
          onChange={handleChange('location')}
          required
        />
      </div>
      
      <button type="submit" disabled={isUpdating}>
        {isUpdating ? 'Updating...' : 'Update Profile'}
      </button>
      
      {updateError && (
        <div className="error">
          Update failed: {updateError.message}
        </div>
      )}
    </form>
  );
}
```

**Key Features Demonstrated:**
- **Query hook**: `useGetContactInfoQuery()` for fetching data
- **Mutation hook**: `useUpdateContactInfoMutation()` for updating data
- **Loading states**: Different loading indicators for fetch vs update
- **Error handling**: Separate error states for fetch and update operations
- **Form management**: Controlled inputs with proper state management
- **Cache invalidation**: Automatic refetching after successful updates

## Best Practices

### 1. Always Use RTK Query Unless You Have a Specific Reason Not To

```typescript
// ✅ Good: Use RTK Query for standard operations
const { data, error, isLoading } = useGetJobsQuery();

// ❌ Bad: Don't use direct fetch for standard operations
const [data, setData] = useState(null);
useEffect(() => {
  fetch('/api/backend/jobs').then(res => res.json()).then(setData);
}, []);
```

### 2. Define Schemas Before Creating Endpoints

```typescript
// ✅ Good: Schema first
export const NewFeatureSchema = z.object({
  id: z.number(),
  name: z.string(),
});

// Then create endpoint
getNewFeature: builder.query<NewFeature, number>({
  query: (id) => `new-features/${id}`,
  transformResponse: (response: unknown) => {
    return NewFeatureSchema.parse(response);
  },
}),
```

### 3. Use Proper Tag Invalidation for Cache Management

```typescript
// ✅ Good: Specific tag invalidation
createJob: builder.mutation<Job, Partial<Job>>({
  query: (jobData) => ({
    url: 'jobs',
    method: 'POST',
    body: jobData,
  }),
  invalidatesTags: [{ type: 'Job', id: 'LIST' }],
}),

// ❌ Bad: Over-invalidation
createJob: builder.mutation<Job, Partial<Job>>({
  // ... query config
  invalidatesTags: [{ type: 'Job', id: 'LIST' }, { type: 'User' }], // Unnecessary
}),
```

### 4. Handle Loading/Error States in Components

```typescript
// ✅ Good: Comprehensive state handling
function MyComponent() {
  const { data, error, isLoading, isFetching } = useGetDataQuery();
  
  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;
  if (!data) return <div>No data</div>;
  
  return (
    <div>
      {isFetching && <div>Refreshing...</div>}
      {/* Component content */}
    </div>
  );
}
```

### 5. Leverage Automatic Refetching and Polling Features

```typescript
// ✅ Good: Use polling for real-time data
const { data } = useGetJobsQuery(undefined, {
  pollingInterval: 30000, // Refetch every 30 seconds
});

// ✅ Good: Use skip for conditional fetching
const { data } = useGetJobQuery(jobId, {
  skip: !jobId, // Only fetch if jobId exists
});
```

## Common Patterns

### Pagination with JobFilters

```typescript
function JobListingsWithPagination() {
  const [filters, setFilters] = useState<JobFilters>({
    page: 1,
    limit: 10
  });
  
  const { data: jobsResponse } = useGetJobsQuery(filters);
  
  const handlePageChange = (page: number) => {
    setFilters(prev => ({ ...prev, page }));
  };
  
  return (
    <div>
      {/* Job listings */}
      {jobsResponse?.jobs.map(job => (
        <JobCard key={job.id} job={job} />
      ))}
      
      {/* Pagination controls */}
      {jobsResponse?.pagination && (
        <Pagination
          currentPage={jobsResponse.pagination.current_page}
          totalPages={jobsResponse.pagination.total_pages}
          onPageChange={handlePageChange}
        />
      )}
    </div>
  );
}
```

### File Uploads with FormData

```typescript
function FileUploader() {
  const [uploadFile, { isLoading }] = useUploadFileMutation();
  
  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      await uploadFile(formData).unwrap();
    } catch (error) {
      console.error('Upload failed:', error);
    }
  };
  
  return (
    <input
      type="file"
      onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
      disabled={isLoading}
    />
  );
}
```

### Optimistic Updates with Mutations

```typescript
function OptimisticTodoList() {
  const { data: todos } = useGetTodosQuery();
  const [updateTodo] = useUpdateTodoMutation();
  
  const handleToggle = async (todoId: number, completed: boolean) => {
    // Optimistic update
    const optimisticTodo = todos?.find(t => t.id === todoId);
    if (optimisticTodo) {
      // Update UI immediately
      // (This would be handled by cache invalidation in real implementation)
    }
    
    try {
      await updateTodo({ id: todoId, completed }).unwrap();
    } catch (error) {
      // Revert optimistic update on failure
      console.error('Update failed:', error);
    }
  };
  
  return (
    <div>
      {todos?.map(todo => (
        <div key={todo.id}>
          <input
            type="checkbox"
            checked={todo.completed}
            onChange={(e) => handleToggle(todo.id, e.target.checked)}
          />
          <span>{todo.text}</span>
        </div>
      ))}
    </div>
  );
}
```

### Conditional Fetching with Skip

```typescript
function ConditionalDataFetching() {
  const [userId, setUserId] = useState<number | null>(null);
  
  // Only fetch when userId is available
  const { data: user, isLoading } = useGetUserQuery(userId!, {
    skip: !userId
  });
  
  return (
    <div>
      <button onClick={() => setUserId(123)}>
        Load User 123
      </button>
      
      {isLoading && <div>Loading user...</div>}
      {user && <div>User: {user.name}</div>}
    </div>
  );
}
```

## Troubleshooting

### Common Issues

1. **RTK Query not refetching after mutation**
   ```typescript
   // ❌ Bad: Missing invalidatesTags
   createItem: builder.mutation<Item, CreateItemRequest>({
     query: (itemData) => ({
       url: 'items',
       method: 'POST',
       body: itemData,
     }),
     // Missing invalidatesTags
   }),
   
   // ✅ Good: Proper cache invalidation
   createItem: builder.mutation<Item, CreateItemRequest>({
     query: (itemData) => ({
       url: 'items',
       method: 'POST',
       body: itemData,
     }),
     invalidatesTags: [{ type: 'Item', id: 'LIST' }],
   }),
   ```

2. **Zod validation errors**
   ```typescript
   // Check if API response matches schema
   transformResponse: (response: unknown) => {
     try {
       return MySchema.parse(response);
     } catch (error) {
       console.error('Validation failed:', error);
       console.error('Response:', response);
       throw error;
     }
   },
   ```

3. **Loading states not updating**
   ```typescript
   // ✅ Good: Use all available states
   const { data, error, isLoading, isFetching, isSuccess, isError } = useGetDataQuery();
   
   // Different loading indicators
   if (isLoading) return <div>Initial loading...</div>;
   if (isFetching) return <div>Refreshing...</div>;
   if (isError) return <div>Error: {error.message}</div>;
   if (isSuccess && !data) return <div>No data</div>;
   ```

4. **TypeScript errors with RTK Query**
   ```typescript
   // Ensure proper typing
   const { data, error, isLoading } = useGetJobsQuery<JobsResponse, JobFilters>();
   
   // Or use the inferred types from the API slice
   const { data, error, isLoading } = useGetJobsQuery();
   // data is automatically typed as JobsResponse | undefined
   ```

### Debug Mode

Enable detailed logging for development:

```typescript
// Add to your app for development
if (process.env.NODE_ENV === 'development') {
  // RTK Query already includes detailed logging in jobsApi.ts
  // Check browser console for request/response details
}
```

### Network Issues

For debugging network problems:

```typescript
// Check if requests are reaching the proxy
console.log('Making request to:', '/api/backend/jobs');

// Check response status
const { data, error, isLoading } = useGetJobsQuery();
console.log('Response status:', { data, error, isLoading });
```

This guide provides comprehensive coverage of how to make backend requests in the Jobmate.Agent application. Always prefer RTK Query for standard operations, and only use direct fetch for streaming, testing, or when you need custom request logic.

## API Usage (Consolidated)

This section consolidates the API usage guidance (previously in `docs/FRONTEND_API_USAGE.md`) and reflects the current frontend code.

### Base

- API base path: `/api/backend/`
- Auth/session handled by the backend; frontend calls the REST endpoints directly.

### Resume APIs (RTK Query)

Hooks are defined in `frontend/src/store/resumesApi.ts`:

```ts
import {
  useGetResumesQuery,
  useUploadResumeMutation,
  useSetDefaultResumeMutation,
  useDeleteResumeMutation,
} from '@/store';

// Fetch user resumes when needed (e.g., drawer open)
const { data, isLoading, error } = useGetResumesQuery();

// Upload
const [uploadResume] = useUploadResumeMutation();
const form = new FormData();
form.append('resume_file', file);
await uploadResume(form).unwrap();

// Set default
const [setDefault] = useSetDefaultResumeMutation();
await setDefault(resumeId).unwrap();

// Delete (non-default only)
const [deleteResume] = useDeleteResumeMutation();
await deleteResume(resumeId).unwrap();
```

Endpoints used by the store:

- `GET /resumes` → list
- `POST /resume/upload` → upload (multipart: `resume_file`)
- `POST /resumes/{id}/set-default` → make default
- `DELETE /resumes/{id}` → delete

### Download URL

The backend exposes a presigned download URL endpoint. Fetch on demand from the UI (Axios example):

```ts
import axios from 'axios';

// GET /api/backend/resume/{id}/download-url → { download_url, filename?, content_type?, file_size?, expires_in? }
const { data } = await axios.get(`/api/backend/resume/${resumeId}/download-url`, {
  headers: { Accept: 'application/json' },
});
const url = data?.download_url as string | undefined;
if (!url) throw new Error('No download URL returned');
window.open(url, '_blank');
```