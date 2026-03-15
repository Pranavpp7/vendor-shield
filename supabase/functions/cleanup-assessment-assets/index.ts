import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.1";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

const ASSESSMENT_ID_PATTERN = /^[a-z0-9-]+$/;

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const anonKey = Deno.env.get("SUPABASE_ANON_KEY")!;
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return new Response(
        JSON.stringify({ error: "Missing authorization header" }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const userClient = createClient(supabaseUrl, anonKey, {
      global: { headers: { Authorization: authHeader } },
    });

    const {
      data: { user },
      error: userError,
    } = await userClient.auth.getUser();

    if (userError || !user) {
      return new Response(
        JSON.stringify({ error: "Unauthorized" }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const { assessmentId } = await req.json();
    const normalizedAssessmentId = String(assessmentId || "").trim();

    if (!normalizedAssessmentId || !ASSESSMENT_ID_PATTERN.test(normalizedAssessmentId)) {
      return new Response(
        JSON.stringify({ error: "Invalid assessmentId" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const admin = createClient(supabaseUrl, serviceRoleKey);
    const bucket = "vendor-documents";

    // List files using Storage API
    const allObjectPaths: string[] = [];
    let offset = 0;
    const pageSize = 100;
    while (true) {
      const { data: listed, error: listError } = await admin.storage
        .from(bucket)
        .list(normalizedAssessmentId, { limit: pageSize, offset });
      if (listError) throw listError;
      if (!listed || listed.length === 0) break;

      for (const item of listed) {
        if (item.name) {
          allObjectPaths.push(`${normalizedAssessmentId}/${item.name}`);
        }
      }
      if (listed.length < pageSize) break;
      offset += pageSize;
    }

    // Remove files in batches
    for (let i = 0; i < allObjectPaths.length; i += 100) {
      const batch = allObjectPaths.slice(i, i + 100);
      const { error: removeError } = await admin.storage.from(bucket).remove(batch);
      if (removeError) throw removeError;
    }

    const { data: docs, error: docsError } = await admin
      .from("documents")
      .select("id")
      .eq("assessment_id", normalizedAssessmentId)
      .eq("user_id", user.id);
    if (docsError) throw docsError;

    const docIds = (docs || []).map((d) => d.id);

    if (docIds.length > 0) {
      const { error: chunksError } = await admin
        .from("document_chunks")
        .delete()
        .in("document_id", docIds);
      if (chunksError) throw chunksError;
    }

    const { error: documentsDeleteError } = await admin
      .from("documents")
      .delete()
      .eq("assessment_id", normalizedAssessmentId)
      .eq("user_id", user.id);
    if (documentsDeleteError) throw documentsDeleteError;

    const { error: runsDeleteError } = await admin
      .from("assessment_runs")
      .delete()
      .eq("assessment_id", normalizedAssessmentId)
      .eq("user_id", user.id);
    if (runsDeleteError) throw runsDeleteError;

    const { error: assessmentDeleteError } = await admin
      .from("assessments")
      .delete()
      .eq("id", normalizedAssessmentId)
      .eq("user_id", user.id);
    if (assessmentDeleteError) throw assessmentDeleteError;

    return new Response(
      JSON.stringify({
        success: true,
        assessmentId: normalizedAssessmentId,
        deletedStorageObjects: objectPaths.length,
        deletedDocuments: docIds.length,
      }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (e) {
    console.error("cleanup-assessment-assets error:", e);
    return new Response(
      JSON.stringify({ error: e instanceof Error ? e.message : "Unknown error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});