package com.taskplatform.common;

/**
 * Cross-cutting constants shared by every module (api-server, and later
 * job-worker / notification-worker). Kept dependency-free on purpose so
 * this class can be used from any module without pulling in Spring.
 */
public final class ApiConstants {

    /**
     * The current public REST API version prefix, e.g. "/api/v1/...".
     * Centralized here so controllers across modules never hard-code it.
     */
    public static final String API_VERSION = "v1";

    public static final String API_BASE_PATH = "/api/" + API_VERSION;

    private ApiConstants() {
        // utility class, not instantiable
    }
}
