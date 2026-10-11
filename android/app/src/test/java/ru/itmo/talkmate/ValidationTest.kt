package ru.itmo.talkmate

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test
import ru.itmo.talkmate.ui.Validation

class ValidationTest {
    @Test
    fun name() {
        assertNull(Validation.name("Эдна"))
        assertEquals("Введите имя", Validation.name("   "))
    }

    @Test
    fun email() {
        assertNull(Validation.email("johndoe@example.com"))
        assertNull(Validation.email("  edna@itmo.ru "))
        assertEquals("Введите email", Validation.email(""))
        listOf("johndoe", "john@doe", "@example.com", "john doe@example.com").forEach {
            assertEquals(it, "Введите корректный email", Validation.email(it))
        }
    }

    @Test
    fun password() {
        assertNull(Validation.password("password"))
        assertNull(Validation.password("123456"))
        assertEquals("Введите пароль", Validation.password(""))
        assertNotNull(Validation.password("12345"))
    }

    @Test
    fun birthDateIsOptional() {
        assertNull(Validation.birthDate(""))
        assertNull(Validation.birthDate("17.05.2001"))
        assertNotNull(Validation.birthDate("17/05/2001"))
    }

    @Test
    fun code() {
        assertNull(Validation.code("123456"))
        assertNull(Validation.code(" 000001 "))
        listOf("", "12345", "1234567", "12a456").forEach { assertNotNull(it, Validation.code(it)) }
    }

    @Test
    fun serverUrl() {
        assertNull(Validation.serverUrl("http://10.0.2.2:5050"))
        assertNull(Validation.serverUrl("https://talkmate.example.com/api"))
        assertNotNull(Validation.serverUrl("10.0.2.2:5050"))
        assertNotNull(Validation.serverUrl("ftp://host"))
        assertNotNull(Validation.serverUrl(""))
    }
}
