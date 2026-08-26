package com.taskplatform.common;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ApiConstantsTest {

    @Test
    void apiBasePathIsBuiltFromVersion() {
        assertThat(ApiConstants.API_VERSION).isEqualTo("v1");
        assertThat(ApiConstants.API_BASE_PATH).isEqualTo("/api/v1");
    }
}
