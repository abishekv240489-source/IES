package com.pil.ies;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@EnableAsync
@SpringBootApplication
public class IesApplication {
    public static void main(String[] args) {
        SpringApplication.run(IesApplication.class, args);
    }
}
